from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..driver.base import ActionResult, Driver, Observation
from ..guard.domain import blocked_destination
from ..schemas import Action


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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str | None = None


@dataclass(frozen=True)
class StepResult:
    """한 스텝(observe → decide → act)의 기록. AI Orchestrator가 이것을 받아 스텝 로그로 남긴다."""

    observation: Observation
    decision: Decision
    result: ActionResult
    started_at: datetime
    finished_at: datetime

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
    """Driver를 통해 대상 URL에서 태스크 목표를 수행하는 주체."""

    def __init__(
        self,
        persona: dict,
        task: dict,
        driver: Driver,
        decider: Decider,
        allowed_hosts: frozenset[str],
    ) -> None:
        self._persona = persona
        self._task = task
        self._driver = driver
        self._decider = decider
        self._allowed_hosts = allowed_hosts
        self.history: list[StepResult] = []

    async def step(self) -> StepResult:
        started_at = datetime.now().astimezone()
        observation = await self._driver.observe()
        decision = await self._decider.decide(
            self._persona, self._task, observation, list(self.history)
        )
        if decision.action is None:
            # 행동을 얻지 못한 step 은 브라우저에서 아무것도 하지 않고 기록만 남긴다.
            result = ActionResult(ok=False, error=decision.error, error_code=decision.error_code)
        elif destination := blocked_destination(decision.action, observation, self._allowed_hosts):
            # 가드 차단 — 실행하지 않는다. 페이지는 그대로다.
            result = ActionResult(
                ok=False,
                error=f"Action blocked by domain policy: {destination[:200]}",
                error_code="DOMAIN_BLOCKED",
            )
        else:
            result = await self._driver.act(decision.action)
        step_result = StepResult(
            observation=observation,
            decision=decision,
            result=result,
            started_at=started_at,
            finished_at=datetime.now().astimezone(),
        )
        self.history.append(step_result)
        return step_result
