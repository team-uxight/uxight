"""병합 규칙 (GACA-181). 묶는 기준 · 합집합 · 근거 수를 본다."""

import itertools

import pytest

from uxight_agent import bench_metrics
from uxight_agent.diagnose.merge import Diagnosis, keep_by_personas, merge

A = "https://s.example/kor/1/subview.do"
B = "https://s.example/kor/2/subview.do"
C = "https://s.example/kor/3/subview.do"


def evidence(persona_id: int, url: str, step: int = 1) -> dict:
    return {"persona_id": persona_id, "step_from": step, "step_to": step, "url": url}


def diagnosis(*items: dict, taxonomy="navigation_confusion", severity="medium", summary="요약"):
    return Diagnosis(taxonomy, severity, summary, list(items))


def test_same_taxonomy_and_shared_url_become_one_finding() -> None:
    one = diagnosis(evidence(1, A), severity="low", summary="짧은 쪽")
    two = diagnosis(evidence(2, A), evidence(2, B, 2), severity="high", summary="근거가 많은 쪽")

    assert merge([one, two]) == [
        {
            "taxonomy": "navigation_confusion",
            "severity": "high",  # 가장 높은 값
            "summary": "근거가 많은 쪽",
            "evidence": [evidence(1, A), evidence(2, A), evidence(2, B, 2)],
        }
    ]


def test_union_keeps_everything_that_does_not_group() -> None:
    other_type = diagnosis(evidence(1, A), taxonomy="interaction_failure")
    other_url = diagnosis(evidence(2, B))

    assert len(merge([diagnosis(evidence(1, A)), other_type, other_url])) == 3


def test_groups_do_not_depend_on_order() -> None:
    # A-B 와 B-C 가 이어져 셋이 한 진단이다. C 가 먼저 와도, 이어 주는 진단이 나중에 와도 같다.
    items = [
        diagnosis(evidence(1, A)),
        diagnosis(evidence(2, A), evidence(2, B, 2)),
        diagnosis(evidence(3, B), evidence(3, C, 2)),
        diagnosis(evidence(4, C)),
    ]

    for order in itertools.permutations(items):
        (row,) = merge(list(order))
        assert {e["persona_id"] for e in row["evidence"]} == {1, 2, 3, 4}


def test_min_shared_urls_is_a_setting() -> None:
    one = diagnosis(evidence(1, A), evidence(1, B, 2))
    two = diagnosis(evidence(2, A), evidence(2, C, 2))
    three = diagnosis(evidence(3, A), evidence(3, B, 2))

    assert len(merge([one, two])) == 1  # 시작값: 하나라도 겹치면
    assert len(merge([one, two], min_shared_urls=2)) == 2
    assert len(merge([one, three], min_shared_urls=2)) == 1


def test_same_page_ignores_fragment_and_trailing_slash() -> None:
    assert len(merge([diagnosis(evidence(1, A + "#top")), diagnosis(evidence(2, A + "/"))])) == 1


def test_empty_url_is_not_a_shared_url() -> None:
    assert len(merge([diagnosis(evidence(1, "")), diagnosis(evidence(2, ""))])) == 2


def test_same_evidence_is_kept_once() -> None:
    same = evidence(1, A)
    (row,) = merge([diagnosis(same, same), diagnosis(same)])

    assert row["evidence"] == [same]


def test_rows_are_ordered_like_build_findings() -> None:
    rows = merge(
        [
            diagnosis(evidence(1, A), taxonomy="excessive_steps", severity="low"),
            diagnosis(evidence(1, A), taxonomy="task_failure", severity="medium"),
            diagnosis(evidence(1, A), taxonomy="interaction_failure", severity="medium"),
            diagnosis(evidence(1, A), taxonomy="task_failure", severity="high"),
        ]
    )

    assert [(r["taxonomy"], r["severity"]) for r in rows] == [
        ("task_failure", "high"),
        ("interaction_failure", "medium"),
        ("excessive_steps", "low"),
    ]


@pytest.mark.parametrize(("min_personas", "kept"), [(1, 2), (2, 1), (3, 0)])
def test_keep_by_personas_counts_distinct_personas(min_personas: int, kept: int) -> None:
    rows = merge(
        [
            diagnosis(evidence(1, A), evidence(1, B, 2)),  # Persona 1 혼자 — 근거가 둘이어도 1명
            diagnosis(evidence(2, C), taxonomy="task_failure"),
            diagnosis(evidence(3, C), taxonomy="task_failure"),
        ]
    )

    assert len(keep_by_personas(rows, min_personas)) == kept


def test_rows_fit_the_bench_matching_rule() -> None:
    (row,) = merge([diagnosis(evidence(1, A))])
    answers = {"injected": [{"catalog_id": "NAV-L", "page": "/kor/1/subview.do"}]}

    assert set(row) == {"taxonomy", "severity", "summary", "evidence"}
    assert bench_metrics.recall_counts([row], answers) == (1, 1)
