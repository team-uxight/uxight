"""단일 vs 다중 진단 비교 (GACA-181) — 성능 benchmark 가 남긴 로그로 진단자를 돌린다.

    uv run python -m uxight_agent.bench_diagnose <설정> --bench <폴더> --out <폴더> --mode multi

- 실행이 끝난 뒤에 돈다. 같은 실행 로그로 단일 · 다중을 둘 다 재려는 것이다. 그래서 진단 방식은
  bench 변형이 아니고 --mode 로 켜고 끈다. 둘 다 재려면 --mode single --mode multi 로 두 번 쓴다.
- 시작값은 설정이다: --min-personas(근거 수 기준, 2명) · --min-shared-urls(묶는 기준, url 1개).
- bench 처럼 DB 없이 돈다. 운영 Watcher 와 제품 진단은 이 코드를 부르지 않는다.
- 설정 파일은 그 benchmark 를 돌린 것이다. 사이트의 original · answers 로 재현율 · 오탐을 낸다.
- LLM 설정은 운영과 같은 env(LLM_BASE_URL · LLM_API_KEY · LLM_MODEL)다.
- 결과 (--out):
  - summary.md: 진단 방식 × 거르기 × 변형 × 사이트마다 한 행
  - usage.jsonl: LLM 사용량. 역할이 diagnoser_single · diagnoser_multi 라 usage_report 로 나눠 본다
  - <mode>/<run_id>/<persona_id>/steps.jsonl: 배정이 가리키는 로그. bench 의 steps.jsonl 을 나눴다
  - <mode>/<run_id>/messages.jsonl: 회차 기록(배정 · 보고)
  - <mode>/<run_id>/rule-findings.json: 배정의 규칙 검출 번호가 가리키는 행
  - <mode>/<run_id>/findings.json: 합집합. findings-filtered.json: 거기에 근거 수 거르기를 건 것.
    둘 다 findings 표 행의 JSON 배열이다. bench_metrics.recall_counts 에 그대로 넣는다
"""

import argparse
import asyncio
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from . import bench_metrics
from .bench import BenchConfig, Site, commit, load_config
from .diagnose.assign import MODES, Mode, RunDiagnosis, diagnose_run
from .diagnose.diagnoser import MAX_RETRIES, read_jsonl, step_log_path
from .diagnose.merge import MIN_PERSONAS, MIN_SHARED_URLS, keep_by_personas
from .llm import LLMClient, usage_log_path
from .usage_report import load

COLUMNS = (
    "진단", "거르기", "변형", "사이트", "회차", "진단 수", "재현율", "오탐", "배정", "다시 배정",
    "잘린 답", "진단 없이 마감", "버린 근거", "입력 토큰", "출력 토큰", "비용($)", "LLM 시간(s)",
    "걸린 시간(s)",
)  # fmt: skip


@dataclass
class BenchRun:
    """benchmark 회차 하나 — 사이트 × Task × 반복 × 변형."""

    run_id: int
    variant: str
    site: str
    statuses: dict[int | str, str]  # Persona 별 끝난 이유
    steps: dict[int | str, list[dict]]


def load_runs(bench_dir: Path) -> list[BenchRun]:
    """benchmark 결과 폴더의 personas.jsonl · steps.jsonl 을 회차별로 묶는다."""
    runs: dict[int, BenchRun] = {}
    for record in read_jsonl(bench_dir / "personas.jsonl"):
        run_id, persona_id = record["run_id"], record["persona_id"]
        run = runs.setdefault(run_id, BenchRun(run_id, record["variant"], record["site"], {}, {}))
        run.statuses[persona_id] = record["outcome"]
        run.steps[persona_id] = []
    for step in read_jsonl(bench_dir / "steps.jsonl"):
        runs[step["run_id"]].steps[step["persona_id"]].append(step)
    return [runs[run_id] for run_id in sorted(runs)]


def write_step_logs(root: Path, run: BenchRun) -> None:
    """배정이 가리킬 로그를 쓴다. 운영 로그와 같은 root/<run_id>/<persona_id>/steps.jsonl 이다."""
    for persona_id, steps in run.steps.items():
        path = root / step_log_path(run.run_id, persona_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(s, ensure_ascii=False) + "\n" for s in steps]
        path.write_text("".join(lines), encoding="utf-8")


async def diagnose_all(
    llm: LLMClient,
    runs: list[BenchRun],
    modes: list[Mode],
    out: Path,
    min_personas: int,
    min_shared_urls: int,
) -> dict[tuple[Mode, int], RunDiagnosis]:
    """회차마다 진단자를 돌리고 진단 목록을 쓴다. 끝난 회차부터 바로 쓴다."""
    results: dict[tuple[Mode, int], RunDiagnosis] = {}
    for mode in modes:
        root = out / mode
        for run in runs:
            write_step_logs(root, run)
            result = await diagnose_run(llm, root, run.run_id, run.statuses, mode, min_shared_urls)
            results[mode, run.run_id] = result
            folder = root / str(run.run_id)
            rules = [asdict(r) for r in result.rule_findings]
            _write_json(folder / "rule-findings.json", rules)
            _write_json(folder / "findings.json", result.findings)
            filtered = keep_by_personas(result.findings, min_personas)
            _write_json(folder / "findings-filtered.json", filtered)
            closed = f", 진단 없이 마감 {result.closed_personas}" if result.closed_personas else ""
            print(
                f"[{mode}] 회차 {run.run_id} · {run.variant} · {run.site}: "
                f"진단 {len(result.findings)}건, 근거 수 거르기 뒤 {len(filtered)}건{closed}",
                flush=True,
            )
    return results


def summary_rows(
    config: BenchConfig,
    runs: list[BenchRun],
    results: dict[tuple[Mode, int], RunDiagnosis],
    usage: list[dict],
    min_personas: int,
) -> list[dict]:
    """표의 행. 재현율 · 오탐의 정의는 bench_metrics 그대로다. 토큰 · 시간은 합계다."""
    cells: dict[tuple[str, str], list[BenchRun]] = defaultdict(list)
    for run in runs:
        cells[run.variant, run.site].append(run)
    sites = {s.name: s for s in config.sites}
    rows = []
    for mode in dict.fromkeys(m for m, _ in results):
        for (variant, site), members in cells.items():
            done = [results[mode, run.run_id] for run in members]
            ids = {run.run_id for run in members}
            calls = [u for u in usage if u["role"] == f"diagnoser_{mode}" and u["run_id"] in ids]
            spent = _totals(done, calls)
            findings = [f for result in done for f in result.findings]
            filters = {
                "합집합": findings,
                f"근거 수 {min_personas}명": keep_by_personas(findings, min_personas),
            }
            for name, kept in filters.items():
                rows.append(
                    {
                        "mode": mode,
                        "filter": name,
                        "variant": variant,
                        "site": site,
                        "runs": len(members),
                        "findings": len(kept),
                        **_quality(kept, sites[site]),
                        **spent,
                    }
                )
    return rows


def render_table(rows: list[dict]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + " --- |" * len(COLUMNS)]
    for r in rows:
        cost = "—" if r["cost_usd"] is None else f"{r['cost_usd']:.4f}"
        cells = [
            r["mode"], r["filter"], r["variant"], r["site"], r["runs"], r["findings"],
            r["recall"], r["false_positives"], r["assigned"], r["reassigned"], r["truncated"],
            r["closed"], r["dropped_evidence"],
            f"{r['input_tokens']:,}", f"{r['output_tokens']:,}", cost,
            f"{r['llm_seconds']:.1f}", f"{r['seconds']:.1f}",
        ]  # fmt: skip
        lines.append("| " + " | ".join(map(str, cells)) + " |")
    return "\n".join(lines)


def render_summary(
    config: BenchConfig, args: argparse.Namespace, model: str, rows: list[dict]
) -> str:
    return "\n".join(
        [
            f"# 단일 vs 다중 진단 비교 — {config.name}",
            "",
            f"- 날짜: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"- 커밋: {commit()}",
            f"- 모델: {model}",
            f"- benchmark 결과: {args.bench}",
            f"- 묶는 기준: 유형이 같고 근거 url 이 {args.min_shared_urls}개 이상 겹침",
            f"- 근거 수 기준: Persona {args.min_personas}명 이상",
            "- 칸: 재현율 · 오탐의 정의는 uxight_agent/bench_metrics.py. 배정은 다시 배정을 "
            "포함한다. 잘린 답은 출력 한도에 걸려 끊긴 답 수다. 진단 없이 마감은 Persona 수다. "
            "토큰 · 비용 · 시간은 그 행 회차들의 합계이고 "
            "거르기와 상관없이 같다. LLM 시간은 호출마다 걸린 시간의 합, 걸린 시간은 회차마다 "
            "처음부터 끝까지 잰 시간의 합이다.",
            "",
            render_table(rows),
            "",
        ]
    )


def main(argv: list[str] | None = None, llm: LLMClient | None = None) -> int:
    """llm 을 주면 그것을 쓴다 (시험). 안 주면 운영과 같은 env 로 만든다."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config", type=Path, help="그 benchmark 를 돌린 설정 파일 (JSON)")
    ap.add_argument(
        "--bench", type=Path, required=True, help="benchmark 결과 폴더 (personas · steps.jsonl)"
    )
    ap.add_argument("--out", type=Path, required=True, help="결과 폴더 (없거나 비어 있어야 한다)")
    ap.add_argument(
        "--mode",
        action="append",
        choices=MODES,
        required=True,
        help="single = 회차 전체 로그를 진단자 하나에. multi = Persona 별 진단자. 둘 다면 두 번",
    )
    ap.add_argument(
        "--min-personas",
        type=int,
        default=MIN_PERSONAS,
        help="근거 수 기준: 이 수 이상의 Persona 가 겪은 진단만 남긴다",
    )
    ap.add_argument(
        "--min-shared-urls",
        type=int,
        default=MIN_SHARED_URLS,
        help="묶는 기준: 유형이 같고 근거 url 이 이 수 이상 겹치면 같은 진단이다",
    )
    args = ap.parse_args(argv)

    try:
        config = load_config(args.config)
        runs = load_runs(args.bench)
    except (OSError, ValueError, KeyError) as e:
        ap.error(f"설정 파일이나 benchmark 결과를 읽지 못했다: {e!r}")
    if not runs:
        ap.error(f"--bench {args.bench} 에 Persona 기록이 없다")
    if unknown := {r.site for r in runs} - {s.name for s in config.sites}:
        ap.error(f"설정 파일에 없는 사이트: {sorted(unknown)} — 그 benchmark 의 설정 파일을 준다")
    if args.out.exists() and any(args.out.iterdir()):
        ap.error(f"--out {args.out} 이 비어 있지 않다")
    if llm is None:
        try:
            llm = LLMClient(max_retries=MAX_RETRIES)
        except KeyError:
            ap.error("LLM 설정(LLM_BASE_URL · LLM_API_KEY · LLM_MODEL)이 없다")

    args.out.mkdir(parents=True, exist_ok=True)
    # 진단 호출은 운영 사용량 기록과 섞지 않는다 (bench 와 같다).
    usage_env = os.environ.get("LLM_USAGE_LOG")
    os.environ["LLM_USAGE_LOG"] = str(args.out / "usage.jsonl")
    try:
        modes = list(dict.fromkeys(args.mode))
        results = asyncio.run(
            diagnose_all(llm, runs, modes, args.out, args.min_personas, args.min_shared_urls)
        )
        usage = load(usage_log_path())
    finally:
        if usage_env is None:
            os.environ.pop("LLM_USAGE_LOG", None)
        else:
            os.environ["LLM_USAGE_LOG"] = usage_env

    rows = summary_rows(config, runs, results, usage, args.min_personas)
    (args.out / "summary.md").write_text(
        render_summary(config, args, llm.model, rows), encoding="utf-8"
    )
    print(render_table(rows))
    print(f"결과: {args.out}")
    return 0


def _quality(findings: list[dict], site: Site) -> dict:
    """재현율 · 오탐 칸. 정답 파일이 없으면 재현율은 —, 원본 사본이 아니면 오탐은 — 다."""
    recall = "—"
    if site.answers:
        answers = json.loads(site.answers.read_text(encoding="utf-8"))
        found, injected = bench_metrics.recall_counts(findings, answers)
        if injected:
            recall = f"{found / injected:.0%} ({found}/{injected})"
    return {"recall": recall, "false_positives": len(findings) if site.original else "—"}


def _totals(done: list[RunDiagnosis], calls: list[dict]) -> dict:
    costs = [c["cost_usd"] for c in calls]
    return {
        "assigned": sum(d.assigned for d in done),
        "reassigned": sum(d.reassigned for d in done),
        "truncated": sum(d.truncated for d in done),
        "closed": sum(len(d.closed_personas) for d in done),
        "dropped_evidence": sum(d.dropped_evidence for d in done),
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "cost_usd": None if None in costs else sum(costs),
        "llm_seconds": sum(c["latency_ms"] for c in calls) / 1000,
        "seconds": sum(d.seconds for d in done),
    }


def _write_json(path: Path, value: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
