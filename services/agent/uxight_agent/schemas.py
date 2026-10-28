"""서비스 경계의 스키마. LLM 이 낼 수 있는 행동은 아래 5종뿐이다 (agent-safety D18)."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class RunRequest(BaseModel):
    """api → agent: 회차 실행 요청 (내부 API 1). 스냅샷은 runs 행에서 직접 읽는다."""

    run_id: int


class Action(BaseModel):
    """Persona Agent의 결정. element_id는 observe()가 부여한 ID (scroll/back/done은 없어도 된다)."""

    # 모르는 칸은 거부한다 — 모델이 url · selector 같은 칸을 덧붙여도 행동으로 받지 않는다.
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["click", "type", "scroll", "back", "done"]
    element_id: int | None = None
    value: str | None = None  # type: 입력값, scroll: 'up' | 'down'

    @model_validator(mode="after")
    def _required_fields(self) -> Self:
        # 행동마다 꼭 있어야 하는 칸 (행동 로그 명세 4절). 어기면 검증 오류 = INVALID_ACTION.
        if self.kind in ("click", "type") and self.element_id is None:
            raise ValueError(f"{self.kind} needs element_id")
        if self.kind == "type" and self.value is None:
            raise ValueError("type needs value")
        if self.kind == "scroll" and self.value not in ("up", "down"):
            raise ValueError("scroll value must be 'up' or 'down'")
        return self
