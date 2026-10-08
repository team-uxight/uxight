from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..driver.base import ActionResult, Driver, Observation
from ..schemas import Action


@dataclass(frozen=True)
class StepResult:
    """한 스텝(observe → decide → act)의 기록. AI Orchestrator가 이것을 받아 스텝 로그로 남긴다."""

    observation: Observation
    action: Action
    result: ActionResult
    started_at: datetime
    finished_at: datetime


class Decider(ABC):
    """관찰 결과를 보고 다음 행동을 정한다. 스텝마다 정확히 한 번 호출된다."""

    @abstractmethod
    async def decide(
        self, persona: dict, task: dict, observation: Observation, history: list[StepResult]
    ) -> Action:
        """실제 구현에서는 여기서 LLM을 1회 호출한다."""


class MockDecider(Decider):
    """Walking Skeleton용 LLM 대역. observation과 history의 길이만 사용한다."""

    async def decide(
        self, persona: dict, task: dict, observation: Observation, history: list[StepResult]
    ) -> Action:
        if not observation.element_map:
            return Action(kind="scroll", value="down")

        # 스텝마다 다른 요소를 고르도록 순서대로 돌아가며 선택한다.
        element_ids = list(observation.element_map)
        element_id = element_ids[len(history) % len(element_ids)]
        element = observation.element_map[element_id]

        if element["tag"] in ("input", "textarea") and element["type"] not in (
            "submit",
            "button",
            "checkbox",
            "radio",
        ):
            return Action(kind="type", element_id=element_id, value="test")
        return Action(kind="click", element_id=element_id)


class PersonaAgent:
    """Driver를 통해 대상 URL에서 태스크 목표를 수행하는 주체."""

    def __init__(self, persona: dict, task: dict, driver: Driver, decider: Decider) -> None:
        self._persona = persona
        self._task = task
        self._driver = driver
        self._decider = decider
        self.history: list[StepResult] = []

    async def step(self) -> StepResult:
        started_at = datetime.now().astimezone()
        observation = await self._driver.observe()
        action = await self._decider.decide(
            self._persona, self._task, observation, list(self.history)
        )
        result = await self._driver.act(action)
        step_result = StepResult(
            observation=observation,
            action=action,
            result=result,
            started_at=started_at,
            finished_at=datetime.now().astimezone(),
        )
        self.history.append(step_result)
        return step_result
