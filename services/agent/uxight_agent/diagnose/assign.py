"""진단 단계의 Watcher 쪽 (GACA-181) — 배정 · 보고 · 다시 배정 · 회차 기록(messages.jsonl).

단일 vs 다중 진단 비교에서만 쓴다. 운영 Watcher(run_orchestrator)와 제품 진단은 이 코드를 부르지
않는다. 기준은 멀티 에이전트 설계 v0.2 4절이다.

- 단일(single)은 회차 전체 로그와 규칙 검출을 진단자 하나에, 다중(multi)은 Persona 마다 그 Persona
  의 것만 진단자에 배정한다. 진단자 · 병합 규칙은 두 쪽이 같다.
- 같은 단계의 진단자는 서로를 모른다. 진단자가 받는 것은 배정의 로그 경로와 규칙 검출뿐이다.
- 판정 안 함 Persona(실행 오류 · 취소 · 도달 기록이 모두 빔, 11/03 결정)는 배정하지 않는다.
  규칙도 이 Persona 에 Friction 을 만들지 않는다.
- 규칙 검출 한 건은 Persona × 유형이고, 번호는 회차 안에서 붙인다. 단일 · 다중의 번호가 같다.
- 스키마에 안 맞는 보고는 한 번 다시 배정한다. 또 틀리면 결과 없이 마감한다. 맡은 Persona 는 진단
  없이 마감되고(단일이면 회차 전체), 이유는 보고 줄의 error 칸에 남는다.
- 진단자 결과는 '맞음'으로 표시한 규칙 검출과 새로 더한 진단이다.
  - 맞음으로 표시한 규칙 검출: 유형 · 심각도 · 근거는 규칙 값 그대로이고 summary 만 진단자의 것이다.
  - 새로 더한 진단의 근거: 배정한 로그에 그 Persona · step 이 있는 것만 남긴다. url 은 보고 값을
    믿지 않고 step_from 의 로그 값을 쓴다 — 재현율은 이 url 로 맞힌다. 근거가 다 버려지면 진단도
    버린다.
  - 새로 더한 진단의 심각도: 근거 Persona 마다 rule_severity 로 매겨 가장 높은 값을 쓴다.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..llm import LLMClient
from ..watcher.friction_rules import is_unjudged, rule_severity
from .diagnoser import (
    BadReport,
    Evidence,
    Report,
    RuleFinding,
    diagnose,
    read_jsonl,
    step_log_path,
)
from .findings import SEVERITY_RANK, build_findings
from .merge import MIN_SHARED_URLS, Diagnosis, merge

Mode = Literal["single", "multi"]
MODES: tuple[Mode, ...] = ("single", "multi")

# 배정 횟수의 상한. 첫 배정 + 다시 배정 한 번이다.
MAX_ASSIGNMENTS = 2
# 다중에서 동시에 도는 진단자 수. 25명 연구에서 LLM 호출이 한꺼번에 몰리지 않게.
MAX_CONCURRENT_DIAGNOSERS = 5


class MessageLog:
    """회차 기록 <run_id>/messages.jsonl. 한 줄이 배정 또는 보고 하나다."""

    def __init__(self, path: Path, run_id: int) -> None:
        self._path = path
        self._run_id = run_id
        self._count = 0

    def write(
        self,
        act: Literal["assign", "report"],
        sender: str,
        receiver: str,
        content: dict | None,
        reply_to: str | None = None,
        error: str | None = None,
    ) -> str:
        """한 줄을 남기고 id 를 돌려준다. 못 쓰는 보고는 content 가 비고 error 에 이유가 있다."""
        self._count += 1
        message_id = f"m-{self._count:04d}"
        message: dict = {"id": message_id}
        if reply_to:
            message["reply_to"] = reply_to
        message |= {
            "run_id": self._run_id,
            "stage": "diagnose",
            "act": act,
            "from": sender,
            "to": receiver,
            "content": content,
        }
        if error:
            message["error"] = error
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
        return message_id


@dataclass
class RunDiagnosis:
    """회차 하나의 진단 결과. findings 는 합집합이다. 근거 수 거르기는 keep_by_personas 로 건다."""

    rule_findings: list[RuleFinding]
    findings: list[dict]
    assigned: int  # 배정 수. 다시 배정도 센다
    reassigned: int
    closed_personas: list[int | str]  # 진단 없이 마감한 Persona
    dropped_evidence: int  # 로그에 없어 버린 근거 수
    seconds: float


async def diagnose_run(
    llm: LLMClient,
    root: Path,
    run_id: int,
    statuses: dict[int | str, str],
    mode: Mode,
    min_shared_urls: int = MIN_SHARED_URLS,
) -> RunDiagnosis:
    """회차 하나를 진단한다. 로그는 root/<run_id>/<persona_id>/steps.jsonl 에서 읽는다.

    statuses 는 Persona 별 끝난 이유다. 회차 기록은 root/<run_id>/messages.jsonl 에 쓴다.
    """
    started = time.monotonic()
    logs = {p: read_jsonl(root / step_log_path(run_id, p)) for p in statuses}
    logs = {p: steps for p, steps in logs.items() if not is_unjudged(steps, statuses[p])}
    rules = number_rule_findings(logs, statuses)
    # 배정 하나가 맡는 Persona 들
    assignments = [[p] for p in logs] if mode == "multi" else [list(logs)] if logs else []
    messages = MessageLog(root / str(run_id) / "messages.jsonl", run_id)
    slots = asyncio.Semaphore(MAX_CONCURRENT_DIAGNOSERS)

    async def one(persona_ids: list[int | str]) -> tuple[Report | None, int]:
        async with slots:
            return await _assign(llm, root, messages, run_id, mode, persona_ids, rules)

    replies = await asyncio.gather(*(one(persona_ids) for persona_ids in assignments))

    diagnoses: list[Diagnosis] = []
    closed: list[int | str] = []
    dropped = 0
    for persona_ids, (report, _) in zip(assignments, replies, strict=True):
        if report is None:
            closed += persona_ids
            continue
        own_logs = {p: logs[p] for p in persona_ids}
        results, lost = _diagnoser_results(report, rules, own_logs, statuses)
        diagnoses += results
        dropped += lost
    assigned = sum(tries for _, tries in replies)
    return RunDiagnosis(
        rule_findings=rules,
        findings=merge(diagnoses, min_shared_urls),
        assigned=assigned,
        reassigned=assigned - len(assignments),
        closed_personas=closed,
        dropped_evidence=dropped,
        seconds=time.monotonic() - started,
    )


def number_rule_findings(
    logs: dict[int | str, list[dict]], statuses: dict[int | str, str]
) -> list[RuleFinding]:
    """Persona 마다 규칙 검출을 돌려 회차 안 번호를 붙인다. 판정 자체는 friction_rules 그대로다."""
    rules: list[RuleFinding] = []
    for persona_id, steps in logs.items():
        for finding in build_findings({persona_id: steps}, statuses):
            rules.append(
                RuleFinding(
                    finding_id=len(rules) + 1,
                    persona_id=persona_id,
                    taxonomy=finding.taxonomy,
                    severity=finding.severity,
                    reason=finding.hits[0].reason,
                    evidence=finding.evidence,
                )
            )
    return rules


async def _assign(
    llm: LLMClient,
    root: Path,
    messages: MessageLog,
    run_id: int,
    mode: Mode,
    persona_ids: list[int | str],
    rules: list[RuleFinding],
) -> tuple[Report | None, int]:
    """배정 하나를 끝낸다. (보고, 배정 횟수)를 돌려준다. 결과 없이 마감이면 보고가 None 이다."""
    name = f"diagnoser-{persona_ids[0]}" if mode == "multi" else "diagnoser"
    mine = [r for r in rules if r.persona_id in persona_ids]
    step_logs = [step_log_path(run_id, p) for p in persona_ids]
    content = {"step_logs": step_logs, "rule_findings": [r.finding_id for r in mine]}
    persona_id = str(persona_ids[0]) if mode == "multi" else None
    bad_report = None
    for tries in range(1, MAX_ASSIGNMENTS + 1):
        assign_id = messages.write("assign", "master", name, content, reply_to=bad_report)
        try:
            report = await diagnose(
                llm, root, run_id, f"diagnoser_{mode}", persona_id, step_logs, mine
            )
        except BadReport as e:
            bad_report = messages.write(
                "report", name, "master", None, reply_to=assign_id, error=str(e)
            )
            continue
        body = report.model_dump(exclude_none=True)
        messages.write("report", name, "master", body, reply_to=assign_id)
        return report, tries
    return None, MAX_ASSIGNMENTS


def _diagnoser_results(
    report: Report,
    rules: list[RuleFinding],
    logs: dict[int | str, list[dict]],
    statuses: dict[int | str, str],
) -> tuple[list[Diagnosis], int]:
    """보고에서 진단자 결과를 뽑는다. (결과, 로그에 없어 버린 근거 수)를 돌려준다."""
    by_id = {r.finding_id: r for r in rules}
    results = []
    for check in report.rule_checks:
        if check.correct:
            rule = by_id[check.finding_id]
            results.append(Diagnosis(rule.taxonomy, rule.severity, check.summary, rule.evidence))
    dropped = 0
    for finding in report.findings:
        claimed = [_in_log(e, logs) for e in finding.evidence]
        evidence = [e for e in claimed if e is not None]
        dropped += len(claimed) - len(evidence)
        if evidence:
            severity = _severity(finding.taxonomy, evidence, logs, statuses)
            results.append(Diagnosis(finding.taxonomy, severity, finding.summary, evidence))
    return results, dropped


def _in_log(claimed: Evidence, logs: dict[int | str, list[dict]]) -> dict | None:
    """보고의 근거를 로그와 대조한다. 없는 근거면 None 이다."""
    # 모델이 7 을 "7" 로 보내도 같은 Persona 다.
    persona_id = next((p for p in logs if str(p) == str(claimed.persona_id)), None)
    if persona_id is None:
        return None
    urls = {s["step"]: s["url"] for s in logs[persona_id]}
    start, end = claimed.step_from, claimed.step_to
    if start not in urls or end not in urls or start > end:
        return None
    return {"persona_id": persona_id, "step_from": start, "step_to": end, "url": urls[start] or ""}


def _severity(
    taxonomy: str,
    evidence: list[dict],
    logs: dict[int | str, list[dict]],
    statuses: dict[int | str, str],
) -> str:
    personas = {e["persona_id"] for e in evidence}
    values = [rule_severity(taxonomy, len(logs[p]), statuses[p]) for p in personas]
    return min(values, key=SEVERITY_RANK.__getitem__)
