"""서비스 경계의 스키마. LLM 이 낼 수 있는 행동은 아래 5종뿐이다 (agent-safety D18)."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class RunRequest(BaseModel):
    """api → agent: 실행 시작 요청 (fire-and-forget)."""

    run_id: int
    target_url: HttpUrl
    task: str = Field(min_length=1, max_length=1000)


class Action(BaseModel):
    """LLM 의 한 step 출력. Runner 가 검증(도메인 · 파괴적 행동 · 한도)한 뒤에만 실행한다.

    - click / type 은 관측 목록의 번호(element)를 가리킨다 — 셀렉터를 받지 않는다.
    - type 의 value 는 로그에서 마스킹한다.
    """

    action: Literal["click", "type", "scroll", "back", "done"]
    element: int | None = Field(default=None, ge=0, description="관측 목록의 [n]")
    value: str | None = Field(default=None, max_length=500, description="type 입력값")
    direction: Literal["up", "down"] | None = Field(default=None, description="scroll 방향")
    reasoning: str = Field(default="", max_length=2000, description="think-aloud — 진단 입력")
