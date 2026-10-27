"""tests/fixtures/runs 의 step 로그 예시가 행동 로그 명세를 지키는지 본다.

명세는 docs/persona_agent_log_schema.md. 예시는 판정 · 진단(GACA-159~165)의 테스트 입력이라,
예시가 명세에서 벗어나면 그 위에 만든 규칙도 틀어진다.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

RUNS = Path(__file__).parent / "fixtures" / "runs"
TOP = {
    "run_id", "persona_id", "step", "ts", "url", "observation", "reasoning", "action",
    "result", "blocked", "latency_ms", "tokens", "model", "task",
}  # fmt: skip
# error_code → (blocked.is, blocked.reason, action 이 있나) — 명세 3.8
CODES = {
    None: (False, None, True),
    "PARSE_FAILED": (True, "parse_failed", False),
    "INVALID_ACTION": (True, "schema", False),
    "LLM_REQUEST_FAILED": (False, None, False),
    "LLM_REQUEST_TIMEOUT": (False, None, False),
    "DOMAIN_BLOCKED": (True, "domain", True),
    "DESTRUCTIVE_ACTION_BLOCKED": (True, "destructive", True),
    "RATE_LIMIT_EXCEEDED": (True, "rate", True),
    "ELEMENT_NOT_FOUND": (False, None, True),
    "ELEMENT_NOT_INTERACTABLE": (False, None, True),
    "NAVIGATION_TIMEOUT": (False, None, True),
    "BROWSER_ACTION_FAILED": (False, None, True),
}
NEEDS = {
    "click": {"target"},
    "type": {"target", "text"},
    "scroll": {"direction"},
    "back": set(),
    "done": set(),
}

CASES = [
    pytest.param(run_dir, p, id=f"run{run_dir.name}-persona{p['persona_id']}")
    for run_dir in sorted(d for d in RUNS.iterdir() if d.is_dir())
    for p in json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["personas"]
]


def _load(run_dir: Path, persona_id: int) -> list[dict]:
    text = (run_dir / str(persona_id) / "steps.jsonl").read_text(encoding="utf-8")
    assert text.endswith("\n")  # 마지막 줄까지 다 쓴 파일
    return [json.loads(line) for line in text.splitlines()]


@pytest.mark.parametrize(("run_dir", "persona"), CASES)
def test_example_follows_log_schema(run_dir: Path, persona: dict) -> None:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows = _load(run_dir, persona["persona_id"])
    assert (
        [r["step"] for r in rows]
        == list(range(1, len(rows) + 1))
        == list(range(1, persona["steps"] + 1))
    )
    for r in rows:
        assert set(r) == TOP
        assert (r["run_id"], r["persona_id"]) == (run["run_id"], persona["persona_id"])
        assert datetime.fromisoformat(r["ts"]).tzinfo is not None
        shot = f"{r['run_id']}/{r['persona_id']}/step-{r['step']}.png"
        assert r["observation"]["screenshot"] == shot
        code = r["result"]["error_code"]
        blocked, reason, has_action = CODES[code]
        assert (r["blocked"]["is"], r["blocked"]["reason"]) == (blocked, reason)
        assert (r["action"] is not None) == has_action
        assert r["result"]["ok"] == (code is None)
        if code is not None:
            assert r["result"]["url_after"] == r["url"]  # 실패 · 차단 · 미실행이면 제자리
        if r["action"] is not None:
            a = r["action"]
            filled = {k for k in ("target", "text", "direction") if a[k] is not None}
            assert filled == NEEDS[a["kind"]]
            if a["kind"] == "type":
                assert a["text"] == "***"  # 입력값은 가린다
        if blocked or r["action"] is None or r["action"]["kind"] == "done":
            assert r["latency_ms"]["browser"] == 0
        assert r["task"]["url_reached"] == (r["result"]["url_after"] == run["task"]["success_url"])
    last = rows[-1]
    if persona["status"] == "done":
        assert last["action"]["kind"] == "done"
    if persona["status"] == "max_steps":
        assert len(rows) == run["max_steps"]
