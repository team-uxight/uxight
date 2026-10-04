"""판정 · 진단 모델 비교 — 같은 문제집을 모델마다 돌려 정답률 · 형식 · 일관성 · 시간 · 비용을 본다.

    uv run python -m uxight_agent.bakeoff --model luna=openai/gpt-5.6-luna \\
        --model terra=openai/gpt-5.6-terra@OPENROUTER --repeat 3

- --model 이름=모델ID[@접두어]. 접두어가 X 면 X_BASE_URL · X_API_KEY 를 쓴다 (기본 LLM).
- 문제집: eval/cases/{judge,task_check,friction}.jsonl. 정답(label)은 PM 이 붙인다.
- 결과: eval/results/<시각>/ 에 calls.jsonl(응답) · usage.jsonl(토큰) · summary.md(표).
"""

import argparse
import asyncio
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .llm import LLMClient
from .usage_report import cost_usd, price_table

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "cases"


class Judgment(BaseModel):
    success: bool
    evidence: str = Field(max_length=500, description="최종 화면에서 찾은 근거 문장")


class TaskCheck(BaseModel):
    ambiguous: bool
    question: str | None = Field(default=None, description="모호하면 리서처에게 되물을 질문 하나")


class FrictionCall(BaseModel):
    type: Literal[
        "navigation_confusion", "interaction_failure", "task_failure", "excessive_steps", "none"
    ]
    severity: Literal["high", "medium", "low", "none"]
    steps: list[int] = Field(default_factory=list, description="근거 step 번호")


SYSTEM = {
    "judge": (
        "너는 웹 사용성 실험의 성공 판정관이다. 가상 사용자가 Task 를 끝냈는지 판정한다. "
        "가상 사용자의 주장(마지막 행동의 이유)은 믿지 않는다. 최종 화면에 성공 기준이 실제로 "
        "보이는지만 본다. evidence 에는 화면 글에서 근거가 되는 부분을 짧게 인용한다."
    ),
    "task_check": (
        "너는 실험 시작 전에 Task 문장을 검토한다. 대상은 가천대학교 홈페이지 사본이다. "
        "이 문장만 보고 무엇을 찾아야 하는지 하나로 정해지면 ambiguous=false. 찾을 대상이 "
        "여러 가지로 읽히거나, 필요한 조건(어느 부서 · 학기 · 학번 등)이 빠졌거나, 상태를 바꾸는 "
        "행동(신청 · 결제 · 삭제)을 요구하면 ambiguous=true 이고 question 에 되물을 질문을 쓴다."
    ),
    "friction": (
        "너는 가상 사용자의 step 로그를 보고 가장 두드러진 사용성 문제 하나를 고른다. "
        "navigation_confusion = 메뉴 사이를 오가며 헤맴(같은 URL 2회 재방문, back 2회 이상). "
        "interaction_failure = 같은 요소를 눌러도 반응이 없음(반복 클릭 3회, 3 step 진행 없음). "
        "task_failure = 목표에 도달하지 못함(step 상한, 포기). "
        "excessive_steps = 도달했지만 최단 경로보다 훨씬 많은 step(10 step 초과). "
        "문제가 없으면 none. severity: high = 실패하거나 크게 막힘, medium = 눈에 띄게 헤맴, "
        "low = 작은 지연, 문제가 없으면 none. steps 에 근거 step 번호를 적는다."
    ),
}
SCHEMA = {"judge": Judgment, "task_check": TaskCheck, "friction": FrictionCall}
ANSWER_KEY = {"judge": "success", "task_check": "ambiguous", "friction": "type"}


def load_cases(task: str) -> list[dict[str, Any]]:
    lines = (CASES / f"{task}.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def user_message(task: str, case_input: dict[str, Any]) -> str:
    return json.dumps(case_input, ensure_ascii=False, indent=1)


def score(task: str, label: dict[str, Any], answer: dict[str, Any] | None) -> bool:
    key = ANSWER_KEY[task]
    return answer is not None and answer.get(key) == label[key]


def parse_model_arg(arg: str) -> tuple[str, str, str]:
    """'name=model@PREFIX' → (name, model, prefix)."""
    name, rest = arg.split("=", 1)
    model, _, prefix = rest.partition("@")
    return name, model, prefix or "LLM"


async def run_one(llm: LLMClient, task: str, case: dict[str, Any], sem: asyncio.Semaphore) -> dict:
    async with sem:
        messages = [
            {"role": "system", "content": SYSTEM[task]},
            {"role": "user", "content": user_message(task, case["input"])},
        ]
        try:
            resp = await llm.chat(
                messages, role=f"bakeoff_{task}", response_format=SCHEMA[task], max_tokens=2000
            )
            parsed = resp.choices[0].message.parsed
            answer = parsed.model_dump() if parsed is not None else None
            error = None if parsed is not None else "no_parse"
        except Exception as e:  # 형식 실패 · 연결 실패 모두 "답 없음" 으로 센다
            answer, error = None, type(e).__name__
        return {"case": case["id"], "answer": answer, "error": error,
                "correct": score(task, case["label"], answer)}  # fmt: skip


def summarize(calls: list[dict], usage: list[dict]) -> list[dict]:
    """모델 × 과제별 정답률 · 형식 준수 · 일관성 · 시간 · 비용."""
    table = price_table()
    by = defaultdict(list)
    for c in calls:
        by[(c["model"], c["task"])].append(c)
    use = defaultdict(list)
    for u in usage:
        use[(u["model"], u["role"].removeprefix("bakeoff_"))].append(u)
    rows = []
    for (model, task), cs in sorted(by.items()):
        per_case = defaultdict(list)
        for c in cs:
            per_case[c["case"]].append(json.dumps((c["answer"] or {}).get(ANSWER_KEY[task])))
        agree = [Counter(v).most_common(1)[0][1] / len(v) for v in per_case.values()]
        us = use[(model, task)]
        costs = [x for x in (cost_usd(u, table) for u in us) if x is not None]
        rows.append({
            "model": model, "task": task, "calls": len(cs),
            "accuracy": sum(c["correct"] for c in cs) / len(cs),
            "valid": sum(c["answer"] is not None for c in cs) / len(cs),
            "consistency": sum(agree) / len(agree),
            "latency_s": median(u["latency_ms"] for u in us) / 1000 if us else None,
            "usd_per_call": sum(costs) / len(costs) if costs else None,
        })  # fmt: skip
    return rows


def render(rows: list[dict]) -> str:
    out = ["| 모델 | 과제 | 호출 | 정답률 | 형식 준수 | 일관성 | 시간(중앙, s) | 호출당 $ |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for r in rows:
        lat = f"{r['latency_s']:.1f}" if r["latency_s"] is not None else "?"
        usd = f"{r['usd_per_call']:.5f}" if r["usd_per_call"] is not None else "?"
        out.append(
            f"| {r['model']} | {r['task']} | {r['calls']} | {r['accuracy']:.0%} | "
            f"{r['valid']:.0%} | {r['consistency']:.0%} | {lat} | {usd} |"
        )
    return "\n".join(out)


async def main_async(args: argparse.Namespace) -> Path:
    out_dir = ROOT / "eval" / "results" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True)
    os.environ["LLM_USAGE_LOG"] = str(out_dir / "usage.jsonl")  # 비교 호출은 따로 기록한다
    sem = asyncio.Semaphore(args.concurrency)
    calls: list[dict] = []
    for spec in args.model:
        name, model, prefix = parse_model_arg(spec)
        client = AsyncOpenAI(
            base_url=os.environ[f"{prefix}_BASE_URL"], api_key=os.environ[f"{prefix}_API_KEY"]
        )
        llm = LLMClient(client=client, model=model)
        for task in args.task:
            jobs = [
                run_one(llm, task, c, sem) for c in load_cases(task) for _ in range(args.repeat)
            ]
            for r in await asyncio.gather(*jobs):
                calls.append({"name": name, "model": model, "task": task, **r})
    (out_dir / "calls.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in calls), encoding="utf-8"
    )
    usage = [json.loads(x) for x in (out_dir / "usage.jsonl").read_text().splitlines() if x]
    report = render(summarize(calls, usage))
    (out_dir / "summary.md").write_text(report + "\n", encoding="utf-8")
    print(report)
    return out_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", action="append", required=True, help="이름=모델ID[@접두어]")
    ap.add_argument("--task", action="append", choices=sorted(SCHEMA), help="기본: 셋 다")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args(argv)
    args.task = args.task or sorted(SCHEMA)
    print(f"결과: {asyncio.run(main_async(args))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
