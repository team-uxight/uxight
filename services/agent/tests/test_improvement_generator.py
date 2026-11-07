"""GACA-168: 개선안 생성기 단위 테스트."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from uxight_agent.improve.generator import generate_improvements

FINDINGS = [
    {
        "finding_id": 10,
        "taxonomy": "navigation_confusion",
        "severity": "medium",
        "summary": "장학금 메뉴를 찾기 어려웠다.",
        "evidence": [
            {
                "persona_id": 1,
                "step_from": 2,
                "step_to": 5,
                "url": "https://school.example.com/student",
            }
        ],
    },
    {
        "finding_id": 11,
        "taxonomy": "excessive_steps",
        "severity": "medium",
        "summary": "장학금 메뉴 탐색에 단계가 많이 소요됐다.",
        "evidence": [
            {
                "persona_id": 2,
                "step_from": 3,
                "step_to": 7,
                "url": "https://school.example.com/student",
            }
        ],
    },
]


def make_option(number, finding_ids=None):
    return {
        "option_no": number,
        "finding_ids": finding_ids or [10],
        "patch_kind": "relabel",
        "patch": {
            "target": f"#scholarship-{number}",
            "new_text": "장학금 신청 안내",
        },
        "rationale": "장학금 메뉴의 이름이 불명확해 탐색이 지연됐다.",
        "effect_metric": "step_count",
    }


class FakeLLM:
    def __init__(self, content, finish_reason="stop"):
        self.content = content
        self.finish_reason = finish_reason
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=self.finish_reason,
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


def generate(llm, findings=None):
    return asyncio.run(
        generate_improvements(
            llm=llm,
            findings=FINDINGS if findings is None else findings,
            previous_patches=[],
            task_goal="장학금 신청 메뉴 찾기",
            run_id=1,
        )
    )


def test_generate_three_options():
    llm = FakeLLM(json.dumps({"options": [make_option(i) for i in range(1, 4)]}))

    result = generate(llm)

    assert len(result) == 3
    assert [item["option_no"] for item in result] == [1, 2, 3]
    assert all(item["fix_cost"] is None for item in result)
    assert all("탐색 단계가 줄어들" in item["expected_effect"] for item in result)
    assert llm.calls[0][1]["role"] == "improvement_generation"


def test_discard_unknown_finding_and_keep_valid_options():
    options = [
        make_option(1, [999]),
        make_option(2, [10]),
        make_option(3, [11]),
    ]
    llm = FakeLLM(json.dumps({"options": options}))

    result = generate(llm)

    assert len(result) == 2
    assert [item["option_no"] for item in result] == [1, 2]
    assert [item["finding_ids"] for item in result] == [[10], [11]]


def test_accept_multiple_evidence_pages_without_llm_page_url():
    findings = [
        FINDINGS[0],
        {
            **FINDINGS[1],
            "evidence": [
                {
                    "persona_id": 2,
                    "step_from": 3,
                    "step_to": 7,
                    "url": "https://school.example.com/another",
                }
            ],
        },
    ]
    llm = FakeLLM(json.dumps({"options": [make_option(1, [10, 11])]}))

    result = generate(llm, findings)

    # page=None인 단위 테스트에서는 페이지 선택 및 DOM 검증을 수행하지 않는다.
    assert len(result) == 1
    assert result[0]["finding_ids"] == [10, 11]
    assert result[0]["patch"]["page_url"] is None


def test_reject_invalid_json():
    llm = FakeLLM("이 페이지는 메뉴를 개선해야 합니다.")

    with pytest.raises(ValueError, match="Invalid improvement response"):
        generate(llm)


def test_reject_truncated_response():
    llm = FakeLLM(
        json.dumps({"options": [make_option(1)]}),
        finish_reason="length",
    )

    with pytest.raises(ValueError, match="Incomplete improvement response"):
        generate(llm)


def test_no_findings_skips_llm():
    llm = FakeLLM("{}")

    assert generate(llm, []) == []
    assert llm.calls == []


def test_llm_prompt_does_not_request_page_url():
    llm = FakeLLM(json.dumps({"options": [make_option(1)]}))

    generate(llm)

    system_prompt = llm.calls[0][0][0]["content"]
    assert "page_url" not in system_prompt


def test_invalid_option_is_discarded_without_losing_valid_option():
    options = [
        make_option(1),
        {
            **make_option(2),
            "patch": {"target": "#invalid"},
            "patch_kind": "relabel",
        },
    ]
    llm = FakeLLM(json.dumps({"options": options}))

    result = generate(llm)

    assert len(result) == 1
    assert result[0]["option_no"] == 1
