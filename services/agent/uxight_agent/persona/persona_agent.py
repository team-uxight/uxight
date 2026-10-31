import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ..driver.base import ActionResult, Driver, Observation
from ..guard.destructive import destructive_reason
from ..guard.domain import blocked_destination, safe_destination
from ..schemas import Action

# 가드 모드 (GACA-180). on = 집행(기본값, 운영), shadow = 막을지 판단만 하고 막지 않는다.
# shadow 는 성능 benchmark(bench.py)에서만 켠다. 운영 Watcher 는 이 값을 넘기지 않는다.
GuardMode = Literal["on", "shadow"]


@dataclass(frozen=True)
class Decision:
    """decide() 의 결과. 행동을 얻지 못했으면 action=None 이고 error_code 에 까닭을 적는다.

    error_code 는 step 로그의 오류 코드다 (행동 로그 명세 3.8): PARSE_FAILED(JSON 이 깨짐) ·
    INVALID_ACTION(행동 스키마 밖) · LLM_REQUEST_FAILED · LLM_REQUEST_TIMEOUT.
    """

    action: Action | None
    reasoning: str | None = None
    error_code: str | None = None
    error: str | None = None
    llm_ms: int = 0
    prompt_tokens: int = 0  # 캐시된 토큰을 포함한 입력 토큰
    cached_tokens: int = 0  # prompt_tokens 중 캐시에서 읽은 만큼 (비용 계산용)
    completion_tokens: int = 0  # 추론 토큰을 포함한 출력 토큰
    model: str | None = None


@dataclass(frozen=True)
class StepResult:
    """한 스텝(observe → decide → act)의 기록. AI Orchestrator가 이것을 받아 스텝 로그로 남긴다.

    guard_block 은 행동 가드(도메인 · 파괴적 행동)가 이 행동을 막을 때의 차단 결과다 (GACA-180).
    집행 모드면 result 와 같다. 그림자 모드면 행동은 실행되고, 이 값은 기록으로만 쓴다.
    step 로그 · 감사 로그에는 쓰지 않는다.
    """

    observation: Observation
    decision: Decision
    result: ActionResult
    started_at: datetime
    finished_at: datetime
    browser_ms: int = 0  # 브라우저 행동 시간. 실행하지 않은 step 은 0
    guard_block: ActionResult | None = None

    @property
    def action(self) -> Action | None:
        return self.decision.action


class Decider(ABC):
    """관찰 결과를 보고 다음 행동을 정한다. 스텝마다 정확히 한 번 호출된다."""

    @abstractmethod
    async def decide(
        self, persona: dict, task: dict, observation: Observation, history: list[StepResult]
    ) -> Decision:
        """실제 구현(LLMDecider)은 여기서 LLM을 1회 호출한다."""


class PersonaAgent:
    """Driver를 통해 대상 URL에서 태스크 목표를 수행하는 주체.

    guard 가 "shadow" 면 행동 가드가 막을 행동도 실행하고 차단 결과는 guard_block 에만 남긴다
    (GACA-180). 그 밖의 값은 모두 집행이다.
    """

    def __init__(
        self,
        persona: dict,
        task: dict,
        driver: Driver,
        decider: Decider,
        allowed_hosts: frozenset[str],
        guard: GuardMode = "on",
    ) -> None:
        self._persona = persona
        self._task = task
        self._driver = driver
        self._decider = decider
        self._allowed_hosts = allowed_hosts
        self._shadow = guard == "shadow"
        self.history: list[StepResult] = []

    async def step(self) -> StepResult:
        started_at = datetime.now().astimezone()
        observation = await self._driver.observe()
        # 관측 전에 주 창이 허용 밖에 와 있어 드라이버가 되돌렸으면(늦은 이동, GACA-224)
        # LLM 을 부르지 않는다. 이 step 은 차단으로만 남고, 다음 step 이 되돌린 화면을 보고 정한다.
        # 행동이 없는 step 이라 '행동을 얻지 못한 step' 으로 센다. 세 번 이어지면 Persona 는 fail.
        decision = (
            Decision(action=None)
            if observation.blocked
            else await self._decider.decide(
                self._persona, self._task, observation, list(self.history)
            )
        )
        browser_ms = 0
        guard_block = None
        if observation.blocked:
            result = ActionResult(
                ok=False,
                error=f"Page moved outside domain policy: {observation.blocked}",
                error_code="DOMAIN_BLOCKED",
                destination=observation.blocked,
                late=True,
            )
        elif decision.action is None:
            # 행동을 얻지 못한 step 은 브라우저에서 아무것도 하지 않고 기록만 남긴다.
            result = ActionResult(ok=False, error=decision.error, error_code=decision.error_code)
        elif (
            guard_block := self._guard_block(decision.action, observation)
        ) is not None and not self._shadow:
            # 가드 차단 — 실행하지 않는다. 페이지는 그대로다.
            result = guard_block
        else:
            # 그림자 모드는 가드가 막을 행동도 실행한다. 막을 결과는 guard_block 에만 남는다.
            # 요청 단계 도메인 차단 · 새 창 규칙 · 늦은 이동 되돌리기는 드라이버에서 그대로 돈다.
            act_start = time.monotonic()
            result = await self._driver.act(decision.action)
            browser_ms = int((time.monotonic() - act_start) * 1000)
        step_result = StepResult(
            observation=observation,
            decision=decision,
            result=result,
            started_at=started_at,
            finished_at=datetime.now().astimezone(),
            browser_ms=browser_ms,
            guard_block=guard_block,
        )
        self.history.append(step_result)
        return step_result

    def _guard_block(self, action: Action, observation: Observation) -> ActionResult | None:
        """행동 가드 둘을 차례로 본다. 막을 행동이면 차단 결과, 아니면 None.

        집행 · 그림자 모드가 같은 판단을 쓴다. 그림자 모드는 막지 않을 뿐이다 (GACA-180).
        """
        if destination := blocked_destination(action, observation, self._allowed_hosts):
            # 허용 밖 링크. 막으면 페이지는 그대로다.
            safe = safe_destination(destination)
            return ActionResult(
                ok=False,
                error=f"Action blocked by domain policy: {safe}",
                error_code="DOMAIN_BLOCKED",
                destination=safe,
            )
        if reason := destructive_reason(action, observation):
            # 되돌릴 수 없는 행동 — 마지막 클릭 직전에 막는다. 페이지는 그대로다.
            return ActionResult(
                ok=False,
                error=f"Action blocked as destructive: {reason}",
                error_code="DESTRUCTIVE_ACTION_BLOCKED",
            )
        return None
