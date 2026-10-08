"""서비스 경계의 스키마. LLM 이 낼 수 있는 행동은 아래 5종뿐이다 (agent-safety D18)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class RunRequest(BaseModel):
    """api → agent: 회차 실행 요청 (내부 API 1). 스냅샷은 runs 행에서 직접 읽는다."""

    run_id: int


class Action(BaseModel):
    """Persona Agent의 결정. element_id는 observe()가 부여한 ID (scroll/back/done은 없어도 된다)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["click", "type", "scroll", "back", "done"]
    element_id: int | None = None
    value: str | None = None  # type: 입력값, scroll: 'up' | 'down'
