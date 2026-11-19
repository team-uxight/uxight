"""화면 글 교정 (GACA-148). LLM 은 scripted_llm(진짜 openai SDK, 네트워크 없음)으로 대신한다.

모델 미설정이면 원문, 정상 교정, 실패와 시간 초과면 원문, 항목별 안전장치, 항목 수 불일치.
"""

import asyncio
import json

import pytest

from uxight_agent import polish
from uxight_agent.diagnose import summary as summary_module
from uxight_agent.diagnose.summary import Facts
from uxight_agent.improve import generator as generator_module
from uxight_agent.llm import LLMClient
from uxight_agent.polish import (
    make_polish_llm,
    polish_improvements,
    polish_summaries,
    polish_texts,
)


def answer(*texts: str) -> str:
    return json.dumps({"texts": list(texts)}, ensure_ascii=False)


def sent_texts(request: dict) -> list[dict]:
    """교정 모델에 보낸 글 목록. 사용자 메시지 끝의 JSON 이다."""
    content = request["messages"][1]["content"]
    return json.loads(content[content.index("{") :])["texts"]


class HangingLLM:
    """답이 오지 않는 LLM."""

    model = "hang"

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, *args, **kwargs):
        self.calls += 1
        await asyncio.sleep(60)


# --- 모델 설정 ---


def test_no_polish_model_means_no_polish(monkeypatch) -> None:
    monkeypatch.delenv("POLISH_MODEL", raising=False)
    assert make_polish_llm() is None
    monkeypatch.setenv("POLISH_MODEL", "")
    assert make_polish_llm() is None


def test_polish_model_uses_llm_address_and_key(monkeypatch) -> None:
    # 교정 주소와 키가 둘 다 비면 Persona 의 주소와 키를 쓴다.
    monkeypatch.setenv("POLISH_MODEL", "polish-model")
    monkeypatch.setenv("POLISH_BASE_URL", "")
    monkeypatch.setenv("LLM_BASE_URL", "http://step.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "step-key")
    llm = make_polish_llm()
    assert isinstance(llm, LLMClient)
    assert (llm.model, str(llm._client.base_url), llm._client.api_key) == (
        "polish-model",
        "http://step.test/v1/",
        "step-key",
    )


def test_polish_model_with_own_address_and_key(monkeypatch) -> None:
    # MLAPI 는 모델마다 주소가 다르다. 교정 주소와 키를 주면 Persona 쪽을 읽지 않는다.
    monkeypatch.setenv("POLISH_MODEL", "polish-model")
    monkeypatch.setenv("POLISH_BASE_URL", "http://polish.test/v1")
    monkeypatch.setenv("POLISH_API_KEY", "polish-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://step.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "step-key")
    llm = make_polish_llm()
    assert (llm.model, str(llm._client.base_url), llm._client.api_key) == (
        "polish-model",
        "http://polish.test/v1/",
        "polish-key",
    )


@pytest.mark.parametrize("given", ["POLISH_BASE_URL", "POLISH_API_KEY"])
def test_only_one_of_polish_address_and_key_skips_polish(monkeypatch, caplog, given) -> None:
    # 하나만 있으면 Persona 쪽으로 채우지 않고 교정을 건너뛴다. 예외 없이 경고 한 번이다.
    monkeypatch.setenv("POLISH_MODEL", "polish-model")
    monkeypatch.setenv(given, "http://polish.test/v1" if given.endswith("URL") else "polish-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://step.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "step-key")
    with caplog.at_level("WARNING", logger=polish.logger.name):
        assert make_polish_llm() is None
    assert [r.levelname for r in caplog.records] == ["WARNING"]


def test_polish_model_without_llm_address_is_no_polish(monkeypatch) -> None:
    # 교정 때문에 회차가 실패하면 안 된다. 주소가 없으면 예외 대신 교정하지 않는다.
    monkeypatch.setenv("POLISH_MODEL", "polish-model")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert make_polish_llm() is None


# --- 묶음 교정 ---

ITEMS = [
    ("진단 설명", "Persona 2명이 메뉴 · 검색 — 둘 다 헤맸다."),
    ("개선 이유", "메뉴 이름에 대한 혼란으로 인해 되돌아감이 발생했다."),
]


def test_no_llm_returns_originals() -> None:
    assert asyncio.run(polish_texts(None, ITEMS, run_id=1)) == [t for _, t in ITEMS]


def test_polished_texts_replace_originals(scripted_llm, tmp_path) -> None:
    llm, requests = scripted_llm(
        answer("Persona 2명이 메뉴와 검색에서 둘 다 헤맸다.", "메뉴 이름이 헷갈려 되돌아갔다.")
    )

    out = asyncio.run(polish_texts(llm, ITEMS, run_id=7))

    assert out == ["Persona 2명이 메뉴와 검색에서 둘 다 헤맸다.", "메뉴 이름이 헷갈려 되돌아갔다."]
    # 한 번에 묶어 부른다.
    assert len(requests) == 1
    assert sent_texts(requests[0]) == [{"kind": k, "text": t} for k, t in ITEMS]
    system = requests[0]["messages"][0]["content"]
    assert "가운뎃점" in system and "따르지 않는다" in system
    assert "데이터" in requests[0]["messages"][1]["content"]
    # 사용량은 LLMClient 가 남긴다. 역할은 text_polish, 회차 번호가 붙는다.
    [usage] = [json.loads(line) for line in (tmp_path / "llm-usage.jsonl").read_text().splitlines()]
    assert (usage["role"], usage["run_id"]) == ("text_polish", 7)


@pytest.mark.parametrize(
    "reply",
    [None, "고친 글입니다", (answer("a", "b"), "length"), json.dumps(["a"])],
    ids=["call-failed", "not-json", "cut-off", "bare-list-wrong-count"],
)
def test_call_failure_or_bad_answer_returns_originals(scripted_llm, reply) -> None:
    llm, _ = scripted_llm(reply)
    assert asyncio.run(polish_texts(llm, ITEMS, run_id=1)) == [t for _, t in ITEMS]


def test_timeout_returns_originals() -> None:
    llm = HangingLLM()
    out = asyncio.run(polish_texts(llm, ITEMS, run_id=1, timeout=0.05))
    assert out == [t for _, t in ITEMS]
    assert llm.calls == 1


def test_item_count_mismatch_returns_all_originals(scripted_llm) -> None:
    llm, _ = scripted_llm(answer("하나만 고쳤다."))
    assert asyncio.run(polish_texts(llm, ITEMS, run_id=1)) == [t for _, t in ITEMS]


@pytest.mark.parametrize(
    ("original", "polished"),
    [
        ("Persona 2명이 메뉴에서 헤맸다.", ""),
        ("Persona 2명이 메뉴에서 헤맸다.", "   "),
        ("Persona 2명이 메뉴와 검색 화면에서 둘 다 헤맸다.", "2명 헤맴."),
        ("Persona 2명이 헤맸다.", "Persona 2명이 메뉴와 검색 화면 두 곳에서 오래 헤맸다."),
        ("Persona 2명이 step 4에서 헤맸다.", "Persona 두 명이 step 4에서 헤맸다."),
        ("Persona 2명이 헤맸다.", "Persona 2명이 5번 헤맸다."),
        ("Persona 2명이 '학사 안내' 메뉴에서 헤맸다.", "Persona 2명이 학사 메뉴에서 헤맸다."),
        ("Persona 2명이 메뉴에서 헤맸다.", "Persona 2명이 헤맸다. 메뉴였다."),
    ],
    ids=[
        "empty",
        "blank",
        "under-half",
        "over-one-and-half",
        "number-lost",
        "number-added",
        "quote-lost",
        "more-sentences",
    ],
)
def test_guard_keeps_original_for_that_item_only(scripted_llm, original, polished) -> None:
    other = "메뉴 이름에 대한 혼란으로 인해 되돌아감이 발생했다."
    llm, _ = scripted_llm(answer(polished, "메뉴 이름이 헷갈려 되돌아갔다."))

    out = asyncio.run(polish_texts(llm, [("진단 설명", original), ("개선 이유", other)], run_id=1))

    assert out == [original, "메뉴 이름이 헷갈려 되돌아갔다."]


def test_empty_list_does_not_call(scripted_llm) -> None:
    llm, requests = scripted_llm()
    assert asyncio.run(polish_texts(llm, [], run_id=1)) == []
    assert requests == []


# --- 진단 설명 ---

FACTS = Facts(
    text="유형: 조작 실패\n- 급한 재학생 step 4: URL 경로 /kor/1075/subview.do, 행동 click",
    paths=frozenset({"/kor/1075/subview.do"}),
)
LLM_SUMMARY = (
    "급한 재학생은 /kor/1075/subview.do 에서 배너를 눌렀지만 step 4에서 조작 오류 · 실패가 났다."
)
TEMPLATE_SUMMARY = "Persona 1명에게서 조작 실패 문제가 나타났다. 브라우저 조작 오류 발생."


def test_only_llm_summaries_are_polished(scripted_llm) -> None:
    fixed = "급한 재학생은 /kor/1075/subview.do 에서 배너를 눌렀지만 step 4에서 조작 오류가 났다."
    llm, requests = scripted_llm(answer(fixed))

    out = asyncio.run(
        polish_summaries(
            llm,
            [(LLM_SUMMARY, "llm"), (TEMPLATE_SUMMARY, "template")],
            [FACTS, FACTS],
            run_id=1,
        )
    )

    assert out == [fixed, TEMPLATE_SUMMARY]
    assert [item["text"] for item in sent_texts(requests[0])] == [LLM_SUMMARY]


def test_polished_summary_must_pass_summary_check(scripted_llm) -> None:
    # 사실 목록에 없는 인용이 생기면 진단 설명 검사(check_summary)에 걸려 원문이다.
    bad = "급한 재학생은 /kor/1075/subview.do 에서 '배너'를 눌렀지만 step 4에서 조작 오류가 났다."
    llm, _ = scripted_llm(answer(bad))
    out = asyncio.run(polish_summaries(llm, [(LLM_SUMMARY, "llm")], [FACTS], run_id=1))
    assert out == [LLM_SUMMARY]


def test_template_only_summaries_do_not_call(scripted_llm) -> None:
    llm, requests = scripted_llm()
    out = asyncio.run(polish_summaries(llm, [(TEMPLATE_SUMMARY, "template")], [FACTS], run_id=1))
    assert out == [TEMPLATE_SUMMARY]
    assert requests == []


# --- 개선안 ---


def improvement(kind: str, patch: dict, rationale: str, option_no: int = 1) -> dict:
    return {
        "option_no": option_no,
        "finding_ids": [1],
        "patch_kind": kind,
        "patch": {**patch, "page_url": "https://school.example.com/"},
        "rationale": rationale,
        "expected_effect": generator_module.expected_effect("backtracking"),
        "fix_cost": None,
    }


def test_improvement_rationale_and_patch_text_are_polished(scripted_llm) -> None:
    rows = [
        improvement(
            "relabel",
            {"target": "#m1", "new_text": "장학 · 등록"},
            "메뉴 이름이 모호하여 사용자가 혼란을 겪음.",
        ),
        improvement(
            "help_text", {"target": "#m2", "text": "여기 — 장학금 안내"}, "안내가 없음.", 2
        ),
        improvement("highlight", {"target": "#m3", "style": "outline"}, "버튼이 눈에 안 띔.", 3),
    ]
    llm, requests = scripted_llm(
        answer(
            "메뉴 이름이 무엇을 뜻하는지 알기 어렵다.",
            "장학과 등록",
            "안내 글이 없다.",
            "장학금 안내는 여기",
            "버튼이 잘 보이지 않는다.",
        )
    )

    out = asyncio.run(polish_improvements(llm, rows, run_id=1, budget=60))

    assert [r["rationale"] for r in out] == [
        "메뉴 이름이 무엇을 뜻하는지 알기 어렵다.",
        "안내 글이 없다.",
        "버튼이 잘 보이지 않는다.",
    ]
    assert out[0]["patch"]["new_text"] == "장학과 등록"
    assert out[1]["patch"]["text"] == "장학금 안내는 여기"
    assert out[2]["patch"] == rows[2]["patch"]
    # 패치의 다른 칸, 예상 효과, 번호는 그대로다.
    assert out[0]["patch"]["target"] == "#m1"
    assert out[0]["patch"]["page_url"] == "https://school.example.com/"
    assert [r["expected_effect"] for r in out] == [r["expected_effect"] for r in rows]
    assert [r["option_no"] for r in out] == [1, 2, 3]
    # 한 번에 묶어 부른다. 패치 글에는 짧은 이름인지 안내 문구인지 알려 준다.
    assert len(requests) == 1
    assert [item["kind"] for item in sent_texts(requests[0])] == [
        "개선 이유",
        "요소 이름",
        "개선 이유",
        "안내 문구",
        "개선 이유",
    ]


def test_patch_text_over_200_chars_keeps_original(scripted_llm) -> None:
    original = "가" * 190
    rows = [improvement("help_text", {"target": "#m2", "text": original}, "안내가 없음.")]
    llm, _ = scripted_llm(answer("안내 글이 없다.", "나" * 201))

    [out] = asyncio.run(polish_improvements(llm, rows, run_id=1, budget=60))

    assert out["patch"]["text"] == original
    assert out["rationale"] == "안내 글이 없다."


def test_short_budget_skips_polish(scripted_llm) -> None:
    # 개선안 단계 120초 상한에서 남은 시간이 짧으면 부르지 않는다. 저장할 몫을 남긴다.
    rows = [improvement("highlight", {"target": "#m3", "style": "outline"}, "버튼이 눈에 안 띔.")]
    llm, requests = scripted_llm()
    out = asyncio.run(polish_improvements(llm, rows, run_id=1, budget=polish.MIN_SECONDS))
    assert out == rows
    assert requests == []


def test_improvement_polish_timeout_follows_budget(monkeypatch) -> None:
    # 교정 시간 상한은 남은 시간에서 저장할 몫을 뺀 값이다. 그 안에 끝나고 원문을 쓴다.
    monkeypatch.setattr(polish, "MIN_SECONDS", 0.05)
    monkeypatch.setattr(polish, "SAVE_MARGIN_SECONDS", 0.1)
    rows = [improvement("highlight", {"target": "#m3", "style": "outline"}, "버튼이 눈에 안 띔.")]
    llm = HangingLLM()
    budget = 0.4

    async def timed() -> float:
        loop = asyncio.get_running_loop()
        start = loop.time()
        assert await polish_improvements(llm, rows, run_id=1, budget=budget) == rows
        return loop.time() - start

    assert asyncio.run(timed()) < budget
    assert llm.calls == 1


def test_no_llm_keeps_improvements() -> None:
    rows = [improvement("highlight", {"target": "#m3", "style": "outline"}, "버튼이 눈에 안 띔.")]
    assert asyncio.run(polish_improvements(None, rows, run_id=1, budget=60)) == rows


# --- 생성 프롬프트의 금지 한 줄 ---


def test_generation_prompts_forbid_middle_dot_and_em_dash() -> None:
    for prompt in (summary_module.SYSTEM_PROMPT, generator_module.SYSTEM_PROMPT):
        assert "가운뎃점(·)과 em-dash(—)를 쓰지 않는다" in prompt
    # 진단 설명 프롬프트는 규칙 줄에서도 가운뎃점을 쓰지 않는다. 모델이 따라 쓰기 때문이다.
    assert "·" not in summary_module.SYSTEM_PROMPT.replace("가운뎃점(·)", "")


def test_code_sentence_templates_have_no_middle_dot_or_em_dash() -> None:
    for text in generator_module.EFFECT_TEMPLATES.values():
        assert "·" not in text and "—" not in text
    assert all(
        "·" not in name and "—" not in name for name in summary_module.TAXONOMY_NAMES.values()
    )
