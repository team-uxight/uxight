"""LLM 사용량 · 비용 리포트 — `LLMClient` 가 남긴 data/llm-usage.jsonl 을 묶어 보여 준다.

    uv run python -m uxight_agent.usage_report                    # 전체, 역할별
    uv run python -m uxight_agent.usage_report --days 1 --by run  # 최근 하루, 실행별
    uv run python -m uxight_agent.usage_report --days 1 --slack --alert-usd 5   # 서버 cron 용

- 단가는 USD / 100만 토큰 (입력, 출력). 기본표에 없는 모델은 env 로 준다:
  LLM_PRICES='{"openai/gpt-5.6-luna": [0.20, 1.20]}'. 단가가 없는 모델은 토큰만 세고 비용은 "?".
- 추론 토큰은 출력 토큰 안에 이미 들어 있다 (따로 더하지 않는다).
- --slack 은 SLACK_WEBHOOK_URL 로 요약 한 덩어리를 보낸다.
  --alert-usd 를 넘으면 맨 앞에 경고를 단다.
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .llm import usage_log_path

# 공개 정가 기준 추정치. 실제 청구는 제공자 쪽 사용량이 기준이다.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {"openai/gpt-5.6-luna": (0.20, 1.20)}
GROUP_KEYS = {"role", "day", "run", "model", "persona"}


def load(path: Path, days: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    since = datetime.now(UTC) - timedelta(days=days) if days else None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if since and datetime.fromisoformat(row["ts"]) < since:
            continue
        rows.append(row)
    return rows


def price_table() -> dict[str, tuple[float, float]]:
    table = dict(DEFAULT_PRICES)
    for model, pair in json.loads(os.environ.get("LLM_PRICES", "{}")).items():
        table[model] = (float(pair[0]), float(pair[1]))
    return table


def cost_usd(row: dict[str, Any], table: dict[str, tuple[float, float]]) -> float | None:
    if row["model"] not in table:
        return None
    p_in, p_out = table[row["model"]]
    return (row["input_tokens"] * p_in + row["output_tokens"] * p_out) / 1_000_000


def _key(row: dict[str, Any], by: str) -> str:
    if by == "day":
        return row["ts"][:10]
    if by == "run":
        return str(row.get("run_id") or "-")
    if by == "persona":
        return str(row.get("persona_id") or "-")
    return str(row[by])


def summarize(rows: list[dict[str, Any]], by: str, table: dict[str, tuple[float, float]]) -> dict:
    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "errors": 0, "input": 0, "output": 0, "reasoning": 0, "usd": 0.0}
    )
    unpriced = 0
    for row in rows:
        g = groups[_key(row, by)]
        g["calls"] += 1
        g["errors"] += 1 if row.get("error") else 0
        g["input"] += row["input_tokens"]
        g["output"] += row["output_tokens"]
        g["reasoning"] += row["reasoning_tokens"]
        usd = cost_usd(row, table)
        if usd is None:
            unpriced += 1
        else:
            g["usd"] += usd
    total = {k: sum(g[k] for g in groups.values()) for k in ("calls", "errors", "input", "output")}
    total["usd"] = sum(g["usd"] for g in groups.values())
    return {"groups": dict(groups), "total": total, "unpriced": unpriced}


def render(summary: dict, by: str, title: str) -> str:
    lines = [
        title,
        f"{by:<14} {'호출':>6} {'실패':>4} {'입력':>10} {'출력':>10} {'추론':>9} {'USD':>8}",
    ]
    ordered = sorted(summary["groups"].items(), key=lambda kv: -kv[1]["usd"])
    for name, g in ordered:
        lines.append(
            f"{name[:14]:<14} {g['calls']:>6} {g['errors']:>4} {g['input']:>10,} "
            f"{g['output']:>10,} {g['reasoning']:>9,} {g['usd']:>8.3f}"
        )
    t = summary["total"]
    lines.append(f"합계: 호출 {t['calls']} · 실패 {t['errors']} · 약 ${t['usd']:.3f}")
    if summary["unpriced"]:
        lines.append(f"단가 없는 모델 {summary['unpriced']}건은 비용에 안 들어갔다 (LLM_PRICES)")
    return "\n".join(lines)


def slack_text(summary: dict, report: str, alert_usd: float | None) -> str:
    over = alert_usd is not None and summary["total"]["usd"] > alert_usd
    head = f":warning: LLM 비용이 기준 ${alert_usd:.2f} 를 넘었습니다\n" if over else ""
    return f"{head}```{report}```"


def post_slack(text: str, url: str) -> None:
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        res.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--log", type=Path, default=None, help="기본: LLM_USAGE_LOG 또는 data/llm-usage.jsonl"
    )
    ap.add_argument("--days", type=int, default=None, help="최근 N일만")
    ap.add_argument("--by", choices=sorted(GROUP_KEYS), default="role")
    ap.add_argument("--slack", action="store_true", help="SLACK_WEBHOOK_URL 로 요약 전송")
    ap.add_argument("--alert-usd", type=float, default=None, help="이 금액을 넘으면 경고")
    args = ap.parse_args(argv)

    rows = load(args.log or usage_log_path(), args.days)
    summary = summarize(rows, args.by, price_table())
    span = f"최근 {args.days}일" if args.days else "전체"
    report = render(summary, args.by, f"LLM 사용량 ({span}, {args.by}별)")
    print(report)
    if args.slack:
        url = os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            print("SLACK_WEBHOOK_URL 이 없어 보내지 않았다", file=sys.stderr)
            return 1
        post_slack(slack_text(summary, report, args.alert_usd), url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
