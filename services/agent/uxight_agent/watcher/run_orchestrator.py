import asyncio
import contextlib
import hashlib
import logging
from collections.abc import AsyncIterator, Awaitable
from typing import Literal, TypeVar

from ..db import settings
from ..driver.dom_driver import DomDriver
from ..guard.domain import allowed_hosts
from ..llm import LLMClient
from ..persona.llm_decider import STEP_MAX_RETRIES, LLMDecider
from ..persona.persona_agent import Decider, PersonaAgent, StepResult
from ..repositories.audit_log_repository import audit_log_repository
from ..repositories.run_persona_repository import PersonaOutcome, run_persona_repository
from ..repositories.run_repository import RunSnapshot, run_repository
from ..schemas import Action
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
# 닫기가 멈춰도 취소 요청 후 10초 안에 종료를 기록한다 — 감시 2초 + 닫기 5초 < 10초.
BROWSER_CLOSE_TIMEOUT_SECONDS = 5

# 프로세스 전역 Persona 동시 상한. 회차마다 세마포어를 만들면 회차가 늘수록 동시 브라우저 수가
# 곱해져 RAM 상한이 무너진다 (architecture §3.1). 모든 회차의 Persona 가 이 자리를 나눠 쓴다.
persona_slots = asyncio.Semaphore(settings.max_concurrent_personas)

# 행동을 얻지 못한 step(파싱 실패 · 스키마 밖 · LLM 호출 실패)이 이만큼 이어지면 Persona 를
# 실패로 끝낸다 (행동 로그 명세 2절 · architecture §5). 키가 만료돼도 max_steps 까지 헛돌지 않게.
MAX_CONSECUTIVE_NO_ACTION = 3

# 실행하지 않은 step 의 오류 코드 → 차단 사유 (행동 로그 명세 3.5 · 3.8).
# LLM 호출 실패(LLM_REQUEST_*)는 차단이 아니다.
BLOCK_REASONS = {
    "PARSE_FAILED": "parse_failed",
    "INVALID_ACTION": "schema",
    "DOMAIN_BLOCKED": "domain",
}

# type 행동의 입력값은 로그에 이 글자로만 남긴다 (GACA-154).
MASKED_TEXT = "***"

# LLM 클라이언트는 첫 회차를 수락할 때 만든다 — LLM 설정(env)이 없는 테스트 · 도구도 이 모듈을
# 불러오게. 프로세스 안 모든 Persona 가 연결 하나를 나눠 쓴다.
_llm: LLMClient | None = None


def llm_client() -> LLMClient:
    """LLM 설정(LLM_BASE_URL · LLM_API_KEY · LLM_MODEL)이 비면 KeyError."""
    global _llm
    if _llm is None:
        _llm = LLMClient(max_retries=STEP_MAX_RETRIES)
    return _llm


def make_decider(run_id: int) -> Decider:
    """Persona 하나의 판단기. 테스트는 이 함수를 바꿔 끼워 LLM 없이 돈다."""
    return LLMDecider(llm_client(), run_id=run_id)


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
            # LLM 설정이 없으면 브라우저를 띄우기 전에 회차를 마감한다 — 띄운 뒤 모든 Persona 가
            # 까닭 없이 fail 로 끝나지 않게.
            try:
                llm_client()
            except KeyError:
                logger.error(
                    "run=%s LLM settings missing (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)", run_id
                )
                self._fail_run(run_id, error="LLM 설정 없음")
                return None
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
            try:
                if run_repository.is_cancel_requested(run_id):
                    logger.warning(
                        "run=%s cancel requested before restart, closing as cancelled", run_id
                    )
                    self._finish_running_personas(run_id, "cancelled")
                    run_repository.cancel_unfinished(run_id)
                else:
                    logger.warning("run=%s interrupted by restart, closing as failed", run_id)
                    self._fail_run(run_id, error="interrupted")
            except Exception:
                # 한 회차의 DB 오류로 나머지 회차를 running 으로 남기지 않는다.
                # 오류가 난 회차는 다음 기동 때 다시 정리된다.
                logger.exception("run=%s restart cleanup failed, skipping", run_id)

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
        hosts = allowed_hosts(target_url, snapshot.allowed_domains)
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
                        hosts,
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

    @staticmethod
    def _refresh_progress(run_id: int) -> None:
        # 진행률은 매번 처음부터 다시 센다. 갱신이 한 번 실패해도 회차를 실패로 만들지 않고
        # 기록만 한다 — 다음 갱신(다른 페르소나 종료, 회차 마감)에서 맞춰진다.
        try:
            run_repository.refresh_progress(run_id)
        except Exception:
            logger.exception("run=%s progress refresh failed", run_id)

    def _finish_run(self, run_id: int) -> None:
        # 마지막 페르소나의 진행률 갱신이 실패했어도 회차를 마감하기 전에 맞춘다.
        self._refresh_progress(run_id)
        statuses = run_persona_repository.get_statuses(run_id)
        # 아직 실행 중인 페르소나가 있으면 런은 running 그대로 둔다. 판정은 모두 종료된 뒤에만 한다.
        if not statuses or "running" in statuses.values():
            logger.warning(
                "run=%s 종료되지 않은 페르소나가 있어 런 상태를 바꾸지 않음: %s", run_id, statuses
            )
            return
        # 어떤 상태로 바뀌었는지는 db.py의 SQL 로그(UPDATE runs SET status ...)에 이어서 남는다.
        logger.info("run=%s 모든 페르소나 종료, 런 상태 판정: %s", run_id, statuses)

        # Persona 일부가 fail · timeout 이어도 회차는 실패가 아니다
        # (architecture §3.3, PM 결정 10/13).
        # 우선순위: 취소(cancelled 가 하나라도) > 실패(모두 fail = 실행 오류) > 완료(그 밖 전부).
        if "cancelled" in statuses.values():
            run_repository.mark_cancelled(run_id)
        elif all(status == "fail" for status in statuses.values()):
            failed_text = ", ".join(
                f"{persona_id}({status})" for persona_id, status in statuses.items()
            )
            run_repository.mark_failed(run_id, error=f"실패한 페르소나: {failed_text}")
        else:
            # 성공률 = Agent 가 스스로 done 을 낸 페르소나 비율 (메인 판정 기준, D21).
            done = sum(1 for status in statuses.values() if status == "done")
            run_repository.mark_done(run_id, success_rate=round(done / len(statuses) * 100, 2))

    async def _run_single_persona(
        self,
        run_id: int,
        target_url: str,
        hosts: frozenset[str],
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
                        run_id,
                        target_url,
                        hosts,
                        task,
                        persona,
                        max_steps,
                        max_seconds,
                        cancel_event,
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
                    # 브라우저 실행 실패, 시작 URL 접근 실패, 스텝 안에서 난 시간 초과
                    # (LLM 호출 하나의 상한 등 — 시간 상한과는 다르다) 등
                    # - 페르소나를 running에 남기지 않는다.
                    logger.exception("run=%s persona=%s 수행 실패", run_id, persona_id)
                    outcome = "fail"

        # 종료 처리는 이 한 곳에서만 한다. 페르소나 상태를 확정한 뒤 런의 progress를 갱신한다.
        run_persona_repository.mark_finished(run_id, persona_id, outcome)
        self._refresh_progress(run_id)

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
    async def _open_driver(
        self, run_id: int, persona_id: int, hosts: frozenset[str]
    ) -> AsyncIterator[DomDriver]:
        """나갈 때 브라우저를 닫되 BROWSER_CLOSE_TIMEOUT_SECONDS 까지만 기다린다."""
        driver = DomDriver(allowed_hosts=hosts)
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
            except Exception:
                # 닫기 실패가 이미 정해진 Persona 결과(done · max_steps · timeout · cancelled)를
                # 덮지 않게 기록만 한다. 덮이면 취소한 회차도 failed 로 보인다.
                logger.exception("run=%s persona=%s browser close failed", run_id, persona_id)

    async def _drive_persona(
        self,
        run_id: int,
        target_url: str,
        hosts: frozenset[str],
        task: dict,
        persona: dict,
        max_steps: int,
        max_seconds: float,
        cancel_event: asyncio.Event,
    ) -> Literal["done", "max_steps", "timeout", "cancelled", "fail"]:
        persona_id = persona["persona_id"]
        step_log_writer.prepare(run_id, persona_id)
        # 어느 경로로 return하든 async with를 빠져나가며 브라우저(컨텍스트, 페이지 포함)를 폐기한다.
        # 시간 상한은 자리를 잡은 뒤 브라우저 시작부터 잰다. 넘으면 진행 중인 스텝을 끊고
        # TimeoutError 로 빠져나간다. 브라우저 닫기는 시간 상한이 풀린 뒤라 그 상한에는 끊기지 않고
        # 닫기 상한(BROWSER_CLOSE_TIMEOUT_SECONDS)만 따른다.
        deadline = asyncio.timeout(max_seconds)
        try:
            async with self._open_driver(run_id, persona_id, hosts) as driver, deadline:
                started, _ = await self._run_unless_cancelled(
                    driver.start(target_url), cancel_event
                )
                if not started:
                    logger.info("run=%s persona=%s 브라우저 시작 중단", run_id, persona_id)
                    return "cancelled"
                agent = PersonaAgent(persona, task, driver, make_decider(run_id), hosts)
                no_action = 0
                # 한 스텝 = observe → decide(LLM 1회) → act.
                # Agent 가 done 을 내거나 max_steps 에 도달하면 종료.
                for step_no in range(1, max_steps + 1):
                    finished, step = await self._run_unless_cancelled(agent.step(), cancel_event)
                    if not finished:
                        # 감시 태스크가 진행 중인 스텝을 중단했다.
                        # 끝나지 않은 스텝이라 로그는 남기지 않는다.
                        logger.info(
                            "run=%s persona=%s 진행 중이던 스텝 %s 중단",
                            run_id,
                            persona_id,
                            step_no,
                        )
                        return "cancelled"
                    # 페르소나가 넘겨준 스텝 결과를 즉시 한 줄로 남긴다.
                    # 도중에 죽어도 그때까지의 스텝은 남는다.
                    # 화면 그림을 먼저 쓰고 그다음 로그 줄을 쓴다 (행동 로그 명세 2절).
                    screenshot = None
                    if step.observation.screenshot is not None:
                        screenshot = step_log_writer.write_screenshot(
                            run_id, persona_id, step_no, step.observation.screenshot
                        )
                    step_log_writer.append(
                        run_id,
                        persona_id,
                        self._to_step_log(
                            run_id, persona_id, step_no, step, task, driver.mode, screenshot
                        ),
                    )
                    run_persona_repository.increment_steps(run_id, persona_id)
                    if step.result.error_code == "DOMAIN_BLOCKED":
                        # 차단은 step 로그와 감사 로그에 같이 남긴다 (architecture §9 L1 · L6).
                        audit_log_repository.add_blocked_action(
                            run_id,
                            persona_id,
                            {
                                "persona_id": persona_id,
                                "step": step_no,
                                "reason": "domain",
                                "action": _action_log(step.action),
                                "url": step.observation.url,
                                "destination": step.result.destination,
                            },
                        )
                    logger.info(
                        "run=%s persona=%s step=%s url=%s action=%s ok=%s error_code=%s",
                        run_id,
                        persona_id,
                        step_no,
                        step.observation.url,
                        _action_log(step.action),
                        step.result.ok,
                        step.result.error_code,
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
                    no_action = no_action + 1 if step.action is None else 0
                    if no_action >= MAX_CONSECUTIVE_NO_ACTION:
                        logger.warning(
                            "run=%s persona=%s %s consecutive steps without action (last %s)",
                            run_id,
                            persona_id,
                            no_action,
                            step.result.error_code,
                        )
                        return "fail"
                    if step.action is not None and step.action.kind == "done":
                        # Agent 가 스스로 과업 완료를 선언했다 = 성공 (메인 판정 기준, D21).
                        return "done"
        except TimeoutError:
            if not deadline.expired():
                # 스텝 안에서 난 다른 시간 초과(LLM 호출 하나에 건 상한 등)는 시간 상한이 아니라
                # 실행 오류(fail)다. 시간 상한으로 세면 모두 실패한 회차가 done 으로 보인다.
                raise
            # 시간 상한 종료는 WARN 으로 남긴다 (설계서 8.3 로그 파일 설계의 AI 모듈 로그 수준).
            logger.warning(
                "run=%s persona=%s exceeded max_seconds=%s", run_id, persona_id, max_seconds
            )
            return "timeout"
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
    def _to_step_log(
        run_id: int,
        persona_id: int,
        step_no: int,
        step: StepResult,
        task: dict,
        mode: str,
        screenshot: str | None,
    ) -> dict:
        """step 하나를 행동 로그 명세(3절)의 14칸으로. 값이 없는 칸도 null 로 쓴다."""
        decision = step.decision
        error_code = step.result.error_code
        if not step.result.ok and error_code is None:
            error_code = "BROWSER_ACTION_FAILED"  # 드라이버가 따로 나누지 않은 브라우저 실패
        url_after = step.result.url_after or step.observation.url
        success_url = task.get("success_url")
        return {
            "run_id": run_id,
            "persona_id": persona_id,
            "step": step_no,
            "ts": step.finished_at.isoformat(timespec="milliseconds"),
            "url": step.observation.url,
            "observation": {
                "mode": mode,
                "screenshot": screenshot,
                # 같은 화면이면 같은 값 — 화면 반복 탐지용. 관측 글(요소 줄) 전체로 만든다.
                "elements_hash": hashlib.sha256(step.observation.dom.encode()).hexdigest()[:16],
                "element_count": len(step.observation.element_map),
            },
            "reasoning": decision.reasoning,
            "action": _action_log(step.action),
            "result": {
                "ok": step.result.ok,
                "url_after": url_after,
                "error": step.result.error,
                "error_code": error_code,
            },
            "blocked": {"is": error_code in BLOCK_REASONS, "reason": BLOCK_REASONS.get(error_code)},
            "latency_ms": {"llm": decision.llm_ms, "browser": step.browser_ms},
            "tokens": {"prompt": decision.prompt_tokens, "completion": decision.completion_tokens},
            "model": decision.model,
            "task": {"url_reached": _same_url(url_after, success_url) if success_url else None},
        }


def _action_log(action: Action | None) -> dict | None:
    """행동을 로그 모양(kind · target · text · direction)으로. type 의 입력값은 가린다."""
    if action is None:
        return None
    return {
        "kind": action.kind,
        "target": action.element_id if action.kind in ("click", "type") else None,
        "text": MASKED_TEXT if action.kind == "type" and action.value is not None else None,
        "direction": action.value if action.kind == "scroll" else None,
    }


def _same_url(url: str, success_url: str) -> bool:
    # 조각(#…)과 끝의 / 는 같은 페이지로 본다.
    def normalize(value: str) -> str:
        return value.split("#", 1)[0].rstrip("/")

    return normalize(url) == normalize(success_url)


run_orchestrator = RunOrchestrator()
