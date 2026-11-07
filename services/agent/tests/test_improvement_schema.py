"""GACA-168 개선안 출력 형식 테스트."""

import pytest
from pydantic import ValidationError

from uxight_agent.improve.schema import ImprovementResponse


def option(number=1, kind="relabel", patch=None):
    if patch is None:
        patch = {"target": "#scholarship", "new_text": "장학금 신청"}
    return {
        "option_no": number,
        "finding_ids": [10],
        "page_url": "https://school.example.com/student",
        "patch_kind": kind,
        "patch": patch,
        "rationale": "메뉴 이름이 불명확해 탐색 과정에서 혼란이 발생했다.",
        "effect_metric": "step_count",
    }


def test_valid_improvement():
    result = ImprovementResponse.model_validate({"options": [option()]})
    assert result.options[0].patch_kind == "relabel"


@pytest.mark.parametrize(
    ("kind", "patch"),
    [
        ("relabel", {"target": "#a", "new_text": "장학금"}),
        ("move", {"target": "#a", "destination": "#b", "position": "first"}),
        ("highlight", {"target": "#a", "style": "outline"}),
        ("help_text", {"target": "#a", "text": "여기에서 신청하세요"}),
    ],
)
def test_all_four_patch_kinds(kind, patch):
    result = ImprovementResponse.model_validate(
        {"options": [option(kind=kind, patch=patch)]}
    )
    assert result.options[0].patch_kind == kind


def test_reject_more_than_three_options():
    with pytest.raises(ValidationError):
        ImprovementResponse.model_validate(
            {"options": [option(i) for i in range(1, 5)]}
        )


def test_reject_nonconsecutive_numbers():
    with pytest.raises(ValidationError):
        ImprovementResponse.model_validate(
            {"options": [option(1), option(3)]}
        )


def test_reject_duplicate_finding_ids():
    invalid = option()
    invalid["finding_ids"] = [10, 10]
    with pytest.raises(ValidationError):
        ImprovementResponse.model_validate({"options": [invalid]})


def test_reject_invalid_patch():
    with pytest.raises(ValidationError):
        ImprovementResponse.model_validate(
            {"options": [option(patch={"target": "#a"})]}
        )


def test_reject_llm_generated_description():
    with pytest.raises(ValidationError):
        ImprovementResponse.model_validate(
            {
                "options": [
                    option(
                        patch={
                            "target": "#a",
                            "new_text": "장학금",
                            "description": "LLM이 만든 설명",
                        }
                    )
                ]
            }
        )


def test_reject_invalid_effect_metric():
    invalid = option()
    invalid["effect_metric"] = "conversion_rate"
    with pytest.raises(ValidationError):
        ImprovementResponse.model_validate({"options": [invalid]})
