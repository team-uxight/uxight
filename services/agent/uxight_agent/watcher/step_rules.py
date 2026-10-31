"""step 하나를 받아 Watcher 가 정하는 것 — 로그 한 줄(행동 로그 명세 14칸) · 과업 도달 · 비용 ·
Persona 를 끝낼지.

운영 Watcher(run_orchestrator)와 성능 benchmark(bench)가 같은 규칙으로 돌도록 여기에 둔다.
DB 모듈(..db)을 불러오지 않는다. 벤치는 DB 설정 없이 돌고 dev DB 에 회차를 남기지 않는다.
"""

import hashlib
from typing import Literal

from ..persona.persona_agent import Decision, StepResult
from ..schemas import Action
from ..usage_report import PriceTable, cost_usd

# 행동을 얻지 못한 step(파싱 실패 · 스키마 밖 · LLM 호출 실패)이 이만큼 이어지면 Persona 를
# 실패로 끝낸다 (행동 로그 명세 2절 · architecture §5). 키가 만료돼도 max_steps 까지 헛돌지 않게.
MAX_CONSECUTIVE_NO_ACTION = 3

# 실행하지 않은 step 의 오류 코드 → 차단 사유 (행동 로그 명세 3.5 · 3.8).
# LLM 호출 실패(LLM_REQUEST_*)는 차단이 아니다.
BLOCK_REASONS = {
    "PARSE_FAILED": "parse_failed",
    "INVALID_ACTION": "schema",
    "DOMAIN_BLOCKED": "domain",
    "DESTRUCTIVE_ACTION_BLOCKED": "destructive",
}

# type 행동의 입력값은 로그에 이 글자로만 남긴다 (GACA-154).
MASKED_TEXT = "***"


def persona_outcome(history: list[StepResult]) -> Literal["done", "fail"] | None:
    """마지막 step 까지 보고 Persona 를 끝낼지 정한다. 더 갈 step 이면 None.

    - "done": done 을 냈다 — Agent 가 스스로 과업 완료를 선언했다 = 성공 (메인 판정 기준, D21).
    - "fail": 행동을 얻지 못한 step 이 MAX_CONSECUTIVE_NO_ACTION 번 이어졌다.
    """
    last = history[-1].action
    if last is not None and last.kind == "done":
        return "done"
    recent = history[-MAX_CONSECUTIVE_NO_ACTION:]
    if len(recent) == MAX_CONSECUTIVE_NO_ACTION and all(s.action is None for s in recent):
        return "fail"
    return None


def to_step_log(
    run_id: int,
    persona_id: int | str,
    step_no: int,
    step: StepResult,
    task: dict,
    mode: str,
    screenshot: str | None,
) -> dict:
    """step 하나를 행동 로그 명세(3절)의 14칸으로. 값이 없는 칸도 null 로 쓴다."""
    decision = step.decision
    error_code = step.result.error_code
    if not step.result.ok and error_code is None:
        error_code = "BROWSER_ACTION_FAILED"  # 드라이버가 따로 나누지 않은 브라우저 실패
    url_after = step.result.url_after or step.observation.url
    success_url = task.get("success_url")

    # 행동 후 URL이 확인되지 않으면 목표 도달 여부를 확정하지 않는다.
    # 행동이 실행되지 않은 경우에는 관측한 현재 URL을 사용한다.
    action_not_executed = step.action is None or (
        step.guard_block is not None and step.guard_block is step.result
    )
    reached_url = step.result.url_after if not action_not_executed else step.observation.url
    return {
        "run_id": run_id,
        "persona_id": persona_id,
        "step": step_no,
        "ts": step.finished_at.isoformat(timespec="milliseconds"),
        "url": step.observation.url,
        "observation": {
            "mode": mode,
            "screenshot": screenshot,
            # 같은 화면이면 같은 값 — 화면 반복 탐지용. 관측 글(요소 줄) 전체로 만든다.
            "elements_hash": hashlib.sha256(step.observation.dom.encode()).hexdigest()[:16],
            "element_count": len(step.observation.element_map),
        },
        "reasoning": decision.reasoning,
        "action": action_log(step.action),
        "result": {
            "ok": step.result.ok,
            "url_after": url_after,
            "error": step.result.error,
            "error_code": error_code,
        },
        "blocked": {"is": error_code in BLOCK_REASONS, "reason": BLOCK_REASONS.get(error_code)},
        "latency_ms": {"llm": decision.llm_ms, "browser": step.browser_ms},
        "tokens": {"prompt": decision.prompt_tokens, "completion": decision.completion_tokens},
        "model": decision.model,
        "task": {
            "url_reached": (
                same_url(reached_url, success_url)
                if reached_url is not None and success_url
                else None
            )
        },
    }


def step_cost_usd(decision: Decision, prices: PriceTable) -> float | None:
    """step 하나의 LLM 비용(USD). 단가표에 없는 모델이면 None — 토큰만 센다."""
    return cost_usd(
        {
            "model": decision.model,
            "input_tokens": decision.prompt_tokens,
            "cached_tokens": decision.cached_tokens,
            "output_tokens": decision.completion_tokens,
        },
        prices,
    )


def action_log(action: Action | None) -> dict | None:
    """행동을 로그 모양(kind · target · text · direction)으로. type 의 입력값은 가린다."""
    if action is None:
        return None
    return {
        "kind": action.kind,
        "target": action.element_id if action.kind in ("click", "type") else None,
        "text": MASKED_TEXT if action.kind == "type" and action.value is not None else None,
        "direction": action.value if action.kind == "scroll" else None,
    }


def same_url(url: str, success_url: str) -> bool:
    # 조각(#…)과 끝의 / 는 같은 페이지로 본다.
    def normalize(value: str) -> str:
        return value.split("#", 1)[0].rstrip("/")

    return normalize(url) == normalize(success_url)
