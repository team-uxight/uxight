"""병합 규칙 (GACA-181). Watcher 가 진단자들의 결과를 합친다. 단일 · 다중 모두 같은 코드를 지난다.

- 진단자 하나의 결과는 '맞음'으로 표시한 규칙 검출과 새로 더한 진단이다 (Diagnosis).
- 묶는 기준: 유형이 같고 근거 url 이 min_shared_urls 개 이상 겹치면 같은 진단이다. 시작값은 1개,
  곧 '하나라도 겹치면'이다. 같은 페이지 기준은 성공 판정과 같다(step_rules.page_url).
  A 와 B 가 묶이고 B 와 C 가 묶이면 셋이 한 진단이다. 그래서 순서를 바꿔도 묶음이 같다.
- 합집합(merge): 묶은 진단을 모두 남긴다. 근거는 모두 합치고, 요약은 근거가 가장 많은 쪽의 것을,
  심각도는 가장 높은 값을 쓴다 (findings.py 와 같다). 근거는 같은 것을 뺀 수로 센다.
- 근거 수(keep_by_personas): 묶은 근거에서 그 문제를 겪은 Persona 가 min_personas 명 이상인 진단만
  남긴다. 시작값은 2명이다. 다수결은 쓰지 않는다 — 진단자마다 입력이 달라서, 한 Persona 에서만
  보인 문제를 다수결이 지우게 된다.
- 결과 한 행은 findings 표의 칸(taxonomy · severity · summary · evidence, 키는 snake_case)이다.
  bench_metrics.matches · recall_counts 에 그대로 넣는다.
"""

from dataclasses import dataclass

from ..watcher.step_rules import page_url
from .findings import SEVERITY_RANK, TAXONOMIES

MIN_SHARED_URLS = 1
MIN_PERSONAS = 2


@dataclass(frozen=True)
class Diagnosis:
    """진단자 하나의 결과 한 건."""

    taxonomy: str
    severity: str
    summary: str
    evidence: list[dict]


def merge(diagnoses: list[Diagnosis], min_shared_urls: int = MIN_SHARED_URLS) -> list[dict]:
    """묶는 기준으로 묶어 합집합을 낸다. 순서는 심각도 순, 같으면 유형 정의 순이다."""
    groups: list[list[Diagnosis]] = []
    for diagnosis in diagnoses:
        touching = [
            group
            for group in groups
            if any(_same_problem(diagnosis, other, min_shared_urls) for other in group)
        ]
        groups = [group for group in groups if group not in touching]
        groups.append([other for group in touching for other in group] + [diagnosis])
    rows = [_row(group) for group in groups]
    return sorted(
        rows, key=lambda r: (SEVERITY_RANK[r["severity"]], TAXONOMIES.index(r["taxonomy"]))
    )


def keep_by_personas(findings: list[dict], min_personas: int = MIN_PERSONAS) -> list[dict]:
    """근거에 든 Persona 가 min_personas 명 이상인 진단만 남긴다."""
    return [f for f in findings if len({e["persona_id"] for e in f["evidence"]}) >= min_personas]


def _same_problem(a: Diagnosis, b: Diagnosis, min_shared_urls: int) -> bool:
    return a.taxonomy == b.taxonomy and len(_pages(a) & _pages(b)) >= min_shared_urls


def _pages(diagnosis: Diagnosis) -> set[str]:
    return {page_url(e["url"]) for e in diagnosis.evidence} - {""}


def _unique(evidence: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for item in evidence:
        if item not in kept:
            kept.append(item)
    return kept


def _row(group: list[Diagnosis]) -> dict:
    return {
        "taxonomy": group[0].taxonomy,
        "severity": min((d.severity for d in group), key=SEVERITY_RANK.__getitem__),
        "summary": max(group, key=lambda d: len(_unique(d.evidence))).summary,
        "evidence": _unique([e for d in group for e in d.evidence]),
    }
