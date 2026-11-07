"""GACA-168: LLM이 제안한 UX 개선안의 구조 검증."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from ..patch.schema import Patch

EffectMetric = Literal["success_rate", "step_count", "backtracking"]

_PATCH_ADAPTER = TypeAdapter(Patch)


class ImprovementOption(BaseModel):
    """개선안 하나. 패치는 반드시 하나의 요소를 대상으로 한다."""

    model_config = ConfigDict(extra="forbid")

    option_no: int = Field(ge=1, le=3)
    finding_ids: list[int] = Field(min_length=1)
    page_url: str = Field(min_length=1)
    patch_kind: Literal["relabel", "move", "highlight", "help_text"]
    patch: dict
    rationale: str = Field(min_length=1)
    effect_metric: EffectMetric

    @model_validator(mode="after")
    def validate_patch(self):
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("finding_ids must be unique")

        if "kind" in self.patch or "description" in self.patch:
            raise ValueError("kind and description are not LLM patch parameters")

        _PATCH_ADAPTER.validate_python(
            {**self.patch, "kind": self.patch_kind}
        )
        return self


class ImprovementResponse(BaseModel):
    """한 회차에서 생성하는 개선안 목록."""

    model_config = ConfigDict(extra="forbid")

    options: list[ImprovementOption] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_order(self):
        numbers = [option.option_no for option in self.options]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("option_no must be consecutive, starting at 1")
        return self
