"""회차 진단 묶기 (GACA-165). 예시 회차 9001(tests/fixtures/runs) 의 Persona 5명으로 본다.

규칙 판정 자체는 test_friction_rules.py 가 본다. 여기서는 회차 × 유형 묶기 · 가장 높은 심각도 ·
근거 구간 · 순서만 본다.
"""

import json
from pathlib import Path

from uxight_agent.diagnose.findings import build_findings

RUN_DIR = Path(__file__).parent / "fixtures" / "runs" / "9001"


def load_run() -> tuple[dict[int, list[dict]], dict[int, str]]:
    run = json.loads((RUN_DIR / "run.json").read_text(encoding="utf-8"))
    statuses = {p["persona_id"]: p["status"] for p in run["personas"]}
    steps = {
        persona_id: [
            json.loads(line)
            for line in (RUN_DIR / str(persona_id) / "steps.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        for persona_id in statuses
    }
    return steps, statuses


def step(n: int, url: str) -> dict:
    return {"step": n, "url": url, "action": {"kind": "scroll"}, "result": {}, "task": {}}


def test_one_finding_per_taxonomy_with_highest_severity() -> None:
    findings = build_findings(*load_run())

    # 심각도 순, 같으면 유형 정의 순(길 찾기 혼란 → 조작 실패 → 과제 실패 → 과도한 단계)
    assert [(f.taxonomy, f.severity) for f in findings] == [
        ("task_failure", "high"),  # Persona 3(medium) · 4(high) 중 가장 높은 값
        ("navigation_confusion", "medium"),
        ("interaction_failure", "medium"),
        ("excessive_steps", "low"),
    ]
    assert [sorted({h.persona_id for h in f.hits}) for f in findings] == [
        [3, 4],
        [2, 4],
        [3, 4],
        [2],
    ]
    assert all(f.summary is None for f in findings)


def test_normal_persona_has_no_evidence() -> None:
    # Persona 1 은 최단 경로로 끝난 정상 로그다.
    findings = build_findings(*load_run())

    assert all(e["persona_id"] != 1 for f in findings for e in f.evidence)


def test_evidence_merges_consecutive_steps_into_ranges() -> None:
    # 길 찾기 혼란 Persona 2 의 근거 step 2 · 3 · 6~11 → 구간 2~3, 6~11. url 은 구간 첫 step 의 URL.
    findings = build_findings(*load_run())
    navigation = next(f for f in findings if f.taxonomy == "navigation_confusion")

    assert [e for e in navigation.evidence if e["persona_id"] == 2] == [
        {
            "persona_id": 2,
            "step_from": 2,
            "step_to": 3,
            "url": "https://school.example.com/kor/1104/subview.do",
        },
        {
            "persona_id": 2,
            "step_from": 6,
            "step_to": 11,
            "url": "https://school.example.com/kor/1080/subview.do",
        },
    ]
    # Spring(Finding.evidenceList)이 읽는 키 그대로다.
    assert all(set(e) == {"persona_id", "step_from", "step_to", "url"} for e in navigation.evidence)


def test_empty_logs_and_no_frictions_give_no_findings() -> None:
    # 로그가 빈 Persona 는 건너뛰고, 아무 문제도 없으면 진단 0건이다.
    reached = {**step(1, "https://a.test/"), "task": {"url_reached": True}}

    assert build_findings({1: [], 2: [reached]}, {1: "max_steps", 2: "done"}) == []


def test_unreached_personas_never_leave_zero_findings() -> None:
    # 모두 못 닿고 끝난 회차가 진단 0건이면 '문제 없음'으로 보인다 (11/03 결정의 실패).
    never = [{**step(1, "https://a.test/"), "task": {"url_reached": False}}]
    statuses = {1: "stuck", 2: "timeout", 3: "token_limit"}

    [finding] = build_findings(dict.fromkeys(statuses, never), statuses)

    assert (finding.taxonomy, finding.severity) == ("task_failure", "high")
    assert [h.persona_id for h in finding.hits] == [1, 2, 3]
