"""진단 설명 (GACA-166). 예시 회차 9001 의 진단으로 사실 목록 · 근거 밖 검사 · 대체 문장을 본다.

LLM 은 scripted_llm(진짜 openai SDK, 네트워크 없음)으로 대신한다.
"""

import asyncio

import pytest
from conftest import NO_CHOICES
from test_diagnose_findings import load_run

from uxight_agent.diagnose.findings import build_findings
from uxight_agent.diagnose.summary import (
    MAX_TOKENS,
    build_facts,
    check_summary,
    summarize,
    template_summary,
)

NAMES = {1: "정상", 2: "헤매는 신입생", 3: "급한 재학생", 4: "느린 교직원", 5: "막힌 복학생"}


def finding_and_facts(taxonomy: str):
    steps, statuses = load_run()
    finding = next(f for f in build_findings(steps, statuses) if f.taxonomy == taxonomy)
    return finding, build_facts(finding, steps, "이번 학기 수강신청 기간 찾기", NAMES, 5)


def test_facts_list_task_personas_and_evidence_steps() -> None:
    _, facts = finding_and_facts("interaction_failure")

    assert "유형: 조작 실패" in facts.text
    assert "Task 목표: 이번 학기 수강신청 기간 찾기" in facts.text
    assert "걸린 Persona: 2명 (진단한 Persona 5명)" in facts.text
    # 근거 step 마다 Persona 이름 · URL 경로 · 행동 · 오류 · 판단
    assert (
        "- 급한 재학생 step 4: URL 경로 /kor/1075/subview.do, 행동 click, "
        "오류 ELEMENT_NOT_INTERACTABLE" in facts.text
    )
    assert "/kor/1075/subview.do" in facts.paths
    assert "school.example.com" not in facts.text  # 호스트는 넣지 않는다


GOOD = "급한 재학생은 /kor/1075/subview.do 에서 배너를 눌렀지만 step 4에서 조작 오류가 났다."


@pytest.mark.parametrize(
    ("text", "failed"),
    [
        (GOOD, None),
        ("", "empty"),
        ("가" * 301, "too_long"),
        ("첫 문장이다. 둘째 문장이다. 셋째 문장이다.", "too_many_sentences"),
        ("Persona 9명이 조작에 실패했다.", "unknown_number"),
        ("급한 재학생은 /kor/1157/login.do 에서 막혔다.", "unknown_path"),
        ("급한 재학생은 '로그인' 버튼을 찾지 못했다.", "unknown_quote"),
    ],
    ids=["ok", "empty", "too-long", "three-sentences", "number", "path", "quote"],
)
def test_check_summary_rejects_content_outside_evidence(text: str, failed: str | None) -> None:
    _, facts = finding_and_facts("interaction_failure")

    assert check_summary(text, facts) == failed


def test_quote_from_reasoning_passes_check() -> None:
    # Agent 판단(reasoning)에 있는 말은 따옴표로 옮겨도 근거 안이다.
    _, facts = finding_and_facts("interaction_failure")

    assert (
        check_summary("느린 교직원은 '학사 안내 바로가기'를 눌렀지만 요소를 찾지 못했다.", facts)
        is None
    )


def test_summarize_uses_llm_sentence(scripted_llm) -> None:
    finding, facts = finding_and_facts("interaction_failure")
    llm, requests = scripted_llm(f"  {GOOD}\n")

    text, source = asyncio.run(summarize(llm, finding, facts, run_id=9001))

    assert (text, source) == (GOOD, "llm")
    [request] = requests
    assert request["messages"][1]["content"] == f"사실 목록:\n{facts.text}"
    assert request["max_completion_tokens"] == MAX_TOKENS
    assert "response_format" not in request


@pytest.mark.parametrize(
    "reply",
    [
        None,  # LLM 500
        NO_CHOICES,
        ("급한 재학생은 배너를", "length"),
        ("", "content_filter"),
        "Persona 9명이 조작에 실패했다.",  # 근거 밖 숫자
    ],
    ids=["llm-500", "no-choices", "length", "content-filter", "outside-evidence"],
)
def test_summarize_falls_back_to_rule_sentence(scripted_llm, reply) -> None:
    finding, facts = finding_and_facts("interaction_failure")
    llm, _ = scripted_llm(reply)

    text, source = asyncio.run(summarize(llm, finding, facts))

    assert source == "template"
    assert text == template_summary(finding)


def test_summarize_without_llm_uses_rule_sentence() -> None:
    finding, facts = finding_and_facts("task_failure")

    text, source = asyncio.run(summarize(None, finding, facts))

    # 가장 심한 Persona(high)의 규칙 사유를 붙인다.
    assert source == "template"
    assert (
        text == "Persona 3명에게서 과제 실패 문제가 나타났다. 과제 실행이 max_steps 상태로 종료됨."
    )
