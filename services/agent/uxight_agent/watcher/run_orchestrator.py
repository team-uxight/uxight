import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable
from dataclasses import asdict
from typing import Literal, TypeVar

from ..db import settings
from ..driver.dom_driver import DomDriver
from ..persona.persona_agent import MockDecider, PersonaAgent, StepResult
from ..repositories.run_persona_repository import PersonaOutcome, run_persona_repository
from ..repositories.run_repository import RunSnapshot, run_repository
from .step_log_writer import step_log_writer

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 감시 태스크가 cancel_requested를 확인하고 heartbeat_at을 갱신하는 간격.
# 취소 요청 후 10초 안에 취소되도록 짧게 둔다.
CANCEL_POLL_SECONDS = 2

# policy_snapshot 에 값이 없을 때 쓰는 기본값. Spring 은 null 인 정책 항목을 스냅샷에서 빼고
# AI 모듈의 기본값을 쓰게 한다 (Policy.toSnapshot).
# step 상한 20 — agent-safety §2 한도 · decisions T5. 시간 상한 10분 — architecture §3.3.
DEFAULT_MAX_STEPS = 20
DEFAULT_MAX_SECONDS = 600

# 브라우저 닫기 상한(초). 시간 상한 밖이라 따로 둔다.
BROWSER_CLOSE_TIMEOUT_SECONDS = 10

# 프로세스 전역 Persona 동시 상한. 회차마다 세마포어를 만들면 회차가 늘수록 동시 브라우저 수가
# 곱해져 RAM 상한이 무너진다 (architecture §3.1). 모든 회차의 Persona 가 이 자리를 나눠 쓴다.
persona_slots = asyncio.Semaphore(settings.max_concurrent_personas)

# Walking Skeleton: 실제 LLM 대신 규칙 기반 대역을 쓴다. 상태가 없어 페르소나끼리 공유한다.
decider = MockDecider()


class RunOrchestrator:
    def try_accept_and_start(self, run_id: int) -> RunSnapshot | None:
        """queued 인 회차만 수락한다.

        이미 받은 회차거나 없는 회차면 None. 시작 준비에 실패한 회차도 failed 로 마감하고 None.
        """
        if not run_repository.accept_if_queued(run_id):
            return None
        try:
            snapshot = run_repository.get_snapshot(run_id)
            run_repository.mark_running(run_id)
            run_persona_repository.create_for_persona(
                run_id,
                {
                    persona["persona_id"]: step_log_writer.relative_path(
                        run_id, persona["persona_id"]
                    )
                    for persona in snapshot.personas
                },
            )
        except Exception as exc:
            # 수락한 회차를 accepted · running 으로 남기지 않는다. 호출한 쪽은 None 을 받아
            # failed 상태를 200 으로 응답한다. 예외 문구(SQL · DB 주소)는 로그에만 남긴다.
            # DB 장애로 정리까지 실패하면 예외가 그대로 나가고(500), 남은 회차는 다음 기동 때
            # close_interrupted_runs 가 정리한다.
            logger.exception("run=%s failed to start, closing as failed", run_id)
            self._fail_run(run_id, error=f"실행 오류로 중단: {type(exc).__name__}")
            return None
        return snapshot

    def close_interrupted_runs(self) -> None:
        """agent 시작 시 한 번만 부른다 — 실행 중인 회차가 없을 때여야 한다.

        이전 프로세스가 accepted · running 으로 남긴 회차를 failed 로 마감한다. 취소 요청된 회차는
        cancelled 로 마감한다 (V1__init_schema.sql runs.status 주석). 재개는 하지 않는다
        (architecture §3.3). §3.3 은 같은 스캔에서 queued · accepted 를 집어 실행한다고 적었지만
        다르게 한다 — queued 는 Spring 재전송이 맡으므로 건드리지 않고, accepted 는 수락과 시작
        사이에 멈춘 경우뿐이라 실행하지 않고 running 과 같이 마감한다.
        """
        for run_id in run_repository.get_unfinished_run_ids():
            if run_repository.is_cancel_requested(run_id):
                logger.warning(
                    "run=%s cancel requested before restart, closing as cancelled", run_id
                )
                self._finish_running_personas(run_id, "cancelled")
                run_repository.cancel_unfinished(run_id)
            else:
                logger.warning("run=%s interrupted by restart, closing as failed", run_id)
                self._fail_run(run_id, error="interrupted")

    async def run_personas(self, run_id: int, snapshot: RunSnapshot) -> None:
        # 202 로 수락한 뒤라 여기서 난 예외는 Spring 에 닿지 않는다. 어디서 예외가 나든
        # 회차와 페르소나를 running 으로 남기지 않고 실패로 마감한다.
        try:
            await self._run_all_personas(run_id, snapshot)
        except Exception as exc:
            # 자세한 내용은 로그에만 남긴다 — 예외 문구에는 SQL · DB 주소가 섞일 수 있다.
            logger.exception("run=%s failed, closing as failed", run_id)
            self._fail_run(run_id, error=f"실행 오류로 중단: {type(exc).__name__}")

    async def _run_all_personas(self, run_id: int, snapshot: RunSnapshot) -> None:
        target_url = snapshot.target_url
        task = snapshot.task
        personas = snapshot.personas
        policy = snapshot.policy
        max_steps = policy.get("max_steps") or DEFAULT_MAX_STEPS
        max_seconds = policy.get("max_seconds") or DEFAULT_MAX_SECONDS
        # 회차 안 동시 수. 전역 자리(persona_slots)도 함께 잡으므로 실제 상한은 둘 중 작은 값이다.
        # 값이 없으면 회차 안 제한 없이 전역 상한만 따른다.
        run_slots = asyncio.Semaphore(policy.get("persona_concurrency") or len(personas))
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
                        run_id,
                        target_url,
                        task,
                        persona,
                        max_steps,
                        max_seconds,
                        run_slots,
                        cancel_event,
                    )
                    for persona in personas
                ),
                return_exceptions=True,
            )
        finally:
            watcher.cancel()
        unfinished = []
        for persona, result in zip(personas, results, strict=True):
            if isinstance(result, BaseException):
                logger.error(
                    "run=%s persona=%s 종료 처리 실패",
                    run_id,
                    persona["persona_id"],
                    exc_info=result,
                )
                unfinished.append(persona["persona_id"])
        if unfinished:
            # 종료 처리(DB 기록)가 실패한 페르소나는 running 으로 남아 있을 수 있다.
            raise RuntimeError(f"persona finish failed: {unfinished}")
        self._finish_run(run_id)

    def _fail_run(self, run_id: int, error: str) -> None:
        # running 으로 남은 페르소나를 fail 로 정리한 뒤 회차를 failed 로 마감한다.
        self._finish_running_personas(run_id, "fail")
        run_repository.fail_unfinished(run_id, error=error)

    @staticmethod
    def _finish_running_personas(run_id: int, outcome: PersonaOutcome) -> None:
        for persona_id, status in run_persona_repository.get_statuses(run_id).items():
            if status == "running":
                run_persona_repository.mark_finished(run_id, persona_id, outcome)

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
            # 여기까지 오면 모든 페르소나가 정상 종료(done/max_steps)다.
            # 성공률 = Agent 가 스스로 done 을 낸 페르소나 비율 (메인 판정 기준, D21).
            done = sum(1 for status in statuses.values() if status == "done")
            run_repository.mark_done(run_id, success_rate=round(done / len(statuses) * 100, 2))

    async def _run_single_persona(
        self,
        run_id: int,
        target_url: str,
        task: dict,
        persona: dict,
        max_steps: int,
        max_seconds: float,
        run_slots: asyncio.Semaphore,
        cancel_event: asyncio.Event,
    ) -> None:
        persona_id = persona["persona_id"]
        outcome: PersonaOutcome
        async with self._persona_slot(run_slots, cancel_event) as acquired:
            if not acquired or cancel_event.is_set():
                # 시작 전에 취소된 런 - 브라우저를 띄우지 않고 바로 취소 처리한다.
                logger.info("run=%s persona=%s 시작 전 취소 (브라우저 없음)", run_id, persona_id)
                outcome = "cancelled"
            else:
                try:
                    outcome = await self._drive_persona(
                        run_id, target_url, task, persona, max_steps, max_seconds, cancel_event
                    )
                    if outcome == "cancelled":
                        # _drive_persona는 async with를 빠져나온 뒤 반환하므로
                        # 이 시점엔 브라우저가 이미 닫혀 있다.
                        logger.info(
                            "run=%s persona=%s 브라우저(컨텍스트) 폐기 완료 → 페르소나 취소",
                            run_id,
                            persona_id,
                        )
                except TimeoutError:
                    logger.info(
                        "run=%s persona=%s exceeded max_seconds=%s", run_id, persona_id, max_seconds
                    )
                    outcome = "timeout"
                except Exception:
                    # 브라우저 실행 실패, 시작 URL 접근 실패 등
                    # - 페르소나를 running에 남기지 않는다.
                    logger.exception("run=%s persona=%s 수행 실패", run_id, persona_id)
                    outcome = "fail"

        # 종료 처리는 이 한 곳에서만 한다. 페르소나 상태를 확정한 뒤 런의 progress를 갱신한다.
        run_persona_repository.mark_finished(run_id, persona_id, outcome)
        run_repository.refresh_progress(run_id)

    @contextlib.asynccontextmanager
    async def _persona_slot(
        self, run_slots: asyncio.Semaphore, cancel_event: asyncio.Event
    ) -> AsyncIterator[bool]:
        """회차 자리 → 전역 자리 순으로 잡는다. 전역 자리를 기다리다 취소되면 False."""
        async with run_slots:
            # 전역 자리는 다른 회차의 페르소나가 시간 상한까지 쥐고 있을 수 있다.
            # 기다리는 동안에도 취소 신호를 받아야 취소 요청 후 10초 안에 멈춘다.
            acquired, _ = await self._run_unless_cancelled(persona_slots.acquire(), cancel_event)
            try:
                yield acquired
            finally:
                if acquired:
                    persona_slots.release()

    @contextlib.asynccontextmanager
    async def _open_driver(self, run_id: int, persona_id: int) -> AsyncIterator[DomDriver]:
        """나갈 때 브라우저를 닫되 BROWSER_CLOSE_TIMEOUT_SECONDS 까지만 기다린다."""
        driver = DomDriver()
        try:
            yield driver
        finally:
            # 닫기가 멈추면 자리를 쥔 채 결과 기록까지 막히고, 그동안 감시 태스크가 heartbeat 를
            # 계속 써서 멈춤(stale) 표시도 뜨지 않는다. 상한을 넘으면 브라우저가 남더라도 진행한다.
            try:
                await asyncio.wait_for(driver.close(), BROWSER_CLOSE_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning(
                    "run=%s persona=%s browser close exceeded %ss, continuing",
                    run_id,
                    persona_id,
                    BROWSER_CLOSE_TIMEOUT_SECONDS,
                )

    async def _drive_persona(
        self,
        run_id: int,
        target_url: str,
        task: dict,
        persona: dict,
        max_steps: int,
        max_seconds: float,
        cancel_event: asyncio.Event,
    ) -> Literal["done", "max_steps", "cancelled"]:
        persona_id = persona["persona_id"]
        step_log_writer.prepare(run_id, persona_id)
        # 어느 경로로 return하든 async with를 빠져나가며 브라우저(컨텍스트, 페이지 포함)를 폐기한다.
        # 시간 상한은 자리를 잡은 뒤 브라우저 시작부터 잰다. 넘으면 진행 중인 스텝을 끊고
        # TimeoutError 로 빠져나간다. 브라우저 닫기는 시간 상한이 풀린 뒤라 그 상한에는 끊기지 않고
        # 닫기 상한(BROWSER_CLOSE_TIMEOUT_SECONDS)만 따른다.
        async with self._open_driver(run_id, persona_id) as driver, asyncio.timeout(max_seconds):
            started, _ = await self._run_unless_cancelled(driver.start(target_url), cancel_event)
            if not started:
                logger.info("run=%s persona=%s 브라우저 시작 중단", run_id, persona_id)
                return "cancelled"
            agent = PersonaAgent(persona, task, driver, decider)
            # 한 스텝 = observe → decide(LLM 1회) → act.
            # Agent 가 done 을 내거나 max_steps 에 도달하면 종료.
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
                if step.action.kind == "done":
                    # Agent 가 스스로 과업 완료를 선언했다 = 성공 (메인 판정 기준, D21).
                    return "done"
        return "max_steps"

    async def _watch_cancel(self, run_id: int, cancel_event: asyncio.Event) -> None:
        # 한 스텝(페이지 로드 대기, 이후 LLM 호출 등)이 10초를 넘을 수 있어서,
        # 스텝이 끝날 때만 확인해서는 10초 안에 취소된다고 보장할 수 없다.
        # 짧은 간격으로 따로 확인해 진행 중인 스텝을 중단시킨다.
        # 같은 주기로 heartbeat_at 을 갱신한다 — 스텝이 길어도 살아 있음 신호가 끊기지 않는다.
        # 첫 확인은 기다리지 않고 바로 한다. 실행 전에 취소된 회차는 브라우저를 띄우기 전에 멈춘다.
        while not cancel_event.is_set():
            try:
                if run_repository.is_cancel_requested(run_id):
                    logger.info("run=%s 취소 요청 감지", run_id)
                    cancel_event.set()
                run_repository.touch_heartbeat(run_id)
            except Exception:
                # 일시적인 DB 오류로 감시가 멈추지 않도록 기록만 하고 다음 주기에 다시 확인한다.
                logger.exception("run=%s cancel check or heartbeat failed", run_id)
            await asyncio.sleep(CANCEL_POLL_SECONDS)

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
