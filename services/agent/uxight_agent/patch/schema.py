"""GACA-167: DOM 패치 4종의 JSON 형식과 검증."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PatchText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class PatchBase(BaseModel):
    """모든 패치에 공통으로 적용하는 검증 규칙."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: NonEmptyText
    description: str | None = None


class RelabelPatch(PatchBase):
    """대상 요소의 표시 문구를 변경한다."""

    kind: Literal["relabel"] = "relabel"
    new_text: PatchText


class MovePatch(PatchBase):
    """대상 요소를 다른 요소의 지정된 위치로 이동한다."""

    kind: Literal["move"] = "move"
    destination: NonEmptyText
    position: Literal["before", "after", "first", "last"]


class HighlightPatch(PatchBase):
    """대상 요소에 미리 정의된 강조 스타일을 적용한다."""

    kind: Literal["highlight"] = "highlight"
    style: Literal["outline", "background"]


class HelpTextPatch(PatchBase):
    """대상 요소에 안내 문구를 추가한다."""

    kind: Literal["help_text"] = "help_text"
    text: PatchText


Patch = Annotated[
    RelabelPatch | MovePatch | HighlightPatch | HelpTextPatch,
    Field(discriminator="kind"),
]
