import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import asdict
from typing import Literal, TypeVar

from ..driver.dom_driver import DomDriver
from ..persona.persona_agent import MockDecider, PersonaAgent, StepResult
from ..repositories.run_persona_repository import run_persona_repository
from ..repositories.run_repository import run_repository
from .step_log_writer import step_log_writer

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 감시 태스크가 cancel_requested를 확인하는 간격. 취소 요청 후 10초 안에 취소되도록 짧게 둔다.
CANCEL_POLL_SECONDS = 2

# Walking Skeleton: 실제 LLM 대신 규칙 기반 대역을 쓴다. 상태가 없어 페르소나끼리 공유한다.
decider = MockDecider()


class RunOrchestrator:
    def try_accept_and_start(self, run_id: int, persona_ids: list[int]) -> bool:
        if not run_repository.accept_if_queued(run_id):
            return False
        run_repository.mark_running(run_id)
        run_persona_repository.create_for_persona(
            run_id,
            {
                persona_id: step_log_writer.relative_path(run_id, persona_id)
                for persona_id in persona_ids
            },
        )
        return True

    async def run_personas(
        self, run_id: int, task: dict, personas: list[dict], max_steps: int
    ) -> None:
        target_url = run_repository.get_target_url(run_id)
        # 요청된 페르소나 수만큼 세마포어를 두고 병렬 수행한다.
        semaphore = asyncio.Semaphore(len(personas))
        # 런 단위 취소 신호. 감시 태스크나 스텝 종료 후 확인에서 취소 요청을 발견하면
        # 이 신호를 켜고, 신호가 켜지면 아직 끝나지 않은 페르소나가 모두 멈춘다.
        cancel_event = asyncio.Event()
        watcher = asyncio.create_task(self._watch_cancel(run_id, cancel_event))
        try:
            # 한 페르소나의 예외가 나머지를 끊거나 런 종료 처리를 건너뛰지 않도록
            # 예외도 결과로 받는다.
            results = await asyncio.gather(
                *(
                    self._run_single_persona(
                        run_id, target_url, task, persona, max_steps, semaphore, cancel_event
                    )
                    for persona in personas
                ),
                return_exceptions=True,
            )
        finally:
            watcher.cancel()
        for persona, result in zip(personas, results, strict=True):
            if isinstance(result, BaseException):
                logger.error(
                    "run=%s persona=%s 종료 처리 실패",
                    run_id,
                    persona["persona_id"],
                    exc_info=result,
                )
        self._finish_run(run_id)

    def _finish_run(self, run_id: int) -> None:
        statuses = run_persona_repository.get_statuses(run_id)
        # 아직 실행 중인 페르소나가 있으면 런은 running 그대로 둔다. 판정은 모두 종료된 뒤에만 한다.
        if not statuses or "running" in statuses.values():
            logger.warning(
                "run=%s 종료되지 않은 페르소나가 있어 런 상태를 바꾸지 않음: %s", run_id, statuses
            )
            return
        # 어떤 상태로 바뀌었는지는 db.py의 SQL 로그(UPDATE runs SET status ...)에 이어서 남는다.
        logger.info("run=%s 모든 페르소나 종료, 런 상태 판정: %s", run_id, statuses)

        # 우선순위: 실패(fail/timeout) > 취소(cancelled) > 완료. fail과 cancelled가 섞이면 failed.
        failed = {
            persona_id: status
            for persona_id, status in statuses.items()
            if status in ("fail", "timeout")
        }
        if failed:
            failed_text = ", ".join(
                f"{persona_id}({status})" for persona_id, status in failed.items()
            )
            run_repository.mark_failed(run_id, error=f"실패한 페르소나: {failed_text}")
        elif "cancelled" in statuses.values():
            run_repository.mark_cancelled(run_id)
        else:
            # 여기까지 오면 모든 페르소나가 completed다.
            # Walking Skeleton: 성공 기준이 정해지기 전까지 completed 비율을 성공률로 쓴다.
            completed = sum(1 for status in statuses.values() if status == "completed")
            run_repository.mark_done(run_id, success_rate=round(completed / len(statuses) * 100, 2))

    async def _run_single_persona(
        self,
        run_id: int,
        target_url: str,
        task: dict,
        persona: dict,
        max_steps: int,
        semaphore: asyncio.Semaphore,
        cancel_event: asyncio.Event,
    ) -> None:
        persona_id = persona["persona_id"]
        async with semaphore:
            if cancel_event.is_set():
                # 시작 전에 취소된 런 - 브라우저를 띄우지 않고 바로 취소 처리한다.
                logger.info("run=%s persona=%s 시작 전 취소 (브라우저 없음)", run_id, persona_id)
                outcome = "cancelled"
            else:
                try:
                    outcome = await self._drive_persona(
                        run_id, target_url, task, persona, max_steps, cancel_event
                    )
                    if outcome == "cancelled":
                        # _drive_persona는 async with를 빠져나온 뒤 반환하므로
                        # 이 시점엔 브라우저가 이미 닫혀 있다.
                        logger.info(
                            "run=%s persona=%s 브라우저(컨텍스트) 폐기 완료 → 페르소나 취소",
                            run_id,
                            persona_id,
                        )
                except Exception:
                    # 브라우저 실행 실패, 시작 URL 접근 실패 등
                    # - 페르소나를 running에 남기지 않는다.
                    logger.exception("run=%s persona=%s 수행 실패", run_id, persona_id)
                    outcome = "fail"

        # 종료 처리는 이 한 곳에서만 한다. 페르소나 상태를 확정한 뒤 런의 progress를 갱신한다.
        if outcome == "completed":
            run_persona_repository.mark_completed(run_id, persona_id)
        elif outcome == "cancelled":
            run_persona_repository.mark_cancelled(run_id, persona_id)
        else:
            run_persona_repository.mark_failed(run_id, persona_id)
        run_repository.refresh_progress(run_id)

    async def _drive_persona(
        self,
        run_id: int,
        target_url: str,
        task: dict,
        persona: dict,
        max_steps: int,
        cancel_event: asyncio.Event,
    ) -> Literal["completed", "cancelled"]:
        persona_id = persona["persona_id"]
        step_log_writer.prepare(run_id, persona_id)
        # 어느 경로로 return하든 async with를 빠져나가며 브라우저(컨텍스트, 페이지 포함)를 폐기한다.
        async with DomDriver() as driver:
            started, _ = await self._run_unless_cancelled(driver.start(target_url), cancel_event)
            if not started:
                logger.info("run=%s persona=%s 브라우저 시작 중단", run_id, persona_id)
                return "cancelled"
            agent = PersonaAgent(persona, task, driver, decider)
            # 한 스텝 = observe → decide(LLM 1회) → act. max_steps 도달 또는 성공 기준 충족 시 종료.
            for step_no in range(1, max_steps + 1):
                finished, step = await self._run_unless_cancelled(agent.step(), cancel_event)
                if not finished:
                    # 감시 태스크가 진행 중인 스텝을 중단했다.
                    # 끝나지 않은 스텝이라 로그는 남기지 않는다.
                    logger.info(
                        "run=%s persona=%s 진행 중이던 스텝 %s 중단", run_id, persona_id, step_no
                    )
                    return "cancelled"
                # 페르소나가 넘겨준 스텝 결과를 즉시 한 줄로 남긴다.
                # 도중에 죽어도 그때까지의 스텝은 남는다.
                step_log_writer.append(
                    run_id, persona_id, self._to_step_log(run_id, persona_id, step_no, step)
                )
                run_persona_repository.increment_steps(run_id, persona_id)
                logger.info(
                    "run=%s persona=%s step=%s url=%s action=%r result=%s",
                    run_id,
                    persona_id,
                    step_no,
                    step.observation.url,
                    step.action,
                    step.result,
                )
                # 취소 확인은 로그 저장 이후에 한다. 취소 이전 스텝의 로그를 보존하기 위해서다.
                if run_repository.is_cancel_requested(run_id):
                    logger.info(
                        "run=%s persona=%s 스텝 %s 종료 후 취소 요청 확인",
                        run_id,
                        persona_id,
                        step_no,
                    )
                    cancel_event.set()  # 같은 런의 다른 페르소나도 멈추게 한다.
                    return "cancelled"
                if agent.is_goal_achieved():
                    break
        return "completed"

    async def _watch_cancel(self, run_id: int, cancel_event: asyncio.Event) -> None:
        # 한 스텝(페이지 로드 대기, 이후 LLM 호출 등)이 10초를 넘을 수 있어서,
        # 스텝이 끝날 때만 확인해서는 10초 안에 취소된다고 보장할 수 없다.
        # 짧은 간격으로 따로 확인해 진행 중인 스텝을 중단시킨다.
        while not cancel_event.is_set():
            await asyncio.sleep(CANCEL_POLL_SECONDS)
            try:
                if run_repository.is_cancel_requested(run_id):
                    logger.info("run=%s 취소 요청 감지", run_id)
                    cancel_event.set()
            except Exception:
                # 일시적인 DB 오류로 감시가 멈추지 않도록 기록만 하고 다음 주기에 다시 확인한다.
                logger.exception("run=%s 취소 요청 확인 실패", run_id)

    @staticmethod
    async def _run_unless_cancelled(
        coro: Awaitable[T], cancel_event: asyncio.Event
    ) -> tuple[bool, T | None]:
        """coro를 실행하되 취소 신호가 먼저 오면 중단한다. (끝까지 수행했는지, 결과)를 돌려준다."""
        work = asyncio.ensure_future(coro)
        cancel_wait = asyncio.ensure_future(cancel_event.wait())
        try:
            await asyncio.wait({work, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            work.cancel()
            raise
        finally:
            cancel_wait.cancel()

        if work.done():
            # 둘이 동시에 끝났다면 작업 결과를 쓴다.
            # 취소는 바로 뒤의 스텝 종료 후 확인에서 처리된다.
            return True, work.result()
        work.cancel()
        try:
            await work
        except (asyncio.CancelledError, Exception):
            pass  # 중단된 작업의 결과나 오류는 쓰지 않는다.
        return False, None

    @staticmethod
    def _to_step_log(run_id: int, persona_id: int, step_no: int, step: StepResult) -> dict:
        # 로그 스키마는 미확정. DOM 전문은 크기가 커서 넣지 않고 요소 수와 행동 대상 요소만 남긴다.
        target = step.observation.element_map.get(step.action.element_id)
        return {
            "run_id": run_id,
            "persona_id": persona_id,
            "step": step_no,
            "started_at": step.started_at.isoformat(timespec="milliseconds"),
            "finished_at": step.finished_at.isoformat(timespec="milliseconds"),
            "url": step.observation.url,
            "title": step.observation.title,
            "element_count": len(step.observation.element_map),
            "action": step.action.model_dump(),
            "target": {key: target.get(key) for key in ("tag", "type", "text", "href")}
            if target
            else None,
            "result": asdict(step.result),
        }


run_orchestrator = RunOrchestrator()
