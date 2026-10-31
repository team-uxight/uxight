"""step 하나를 받아 Watcher 가 정하는 것 — 로그 한 줄(행동 로그 명세 14칸) · 과업 도달 · 비용 ·
Persona 를 끝낼지.

운영 Watcher(run_orchestrator)와 성능 benchmark(bench)가 같은 규칙으로 돌도록 여기에 둔다.
DB 모듈(..db)을 불러오지 않는다. 벤치는 DB 설정 없이 돌고 dev DB 에 회차를 남기지 않는다.
"""

import hashlib
from typing import Literal

from ..driver.base import Observation
from ..persona.persona_agent import Decision, StepResult
from ..schemas import Action
from ..usage_report import PriceTable, cost_usd

# 행동을 얻지 못한 step(파싱 실패 · 스키마 밖 · LLM 호출 실패)이 이만큼 이어지면 Persona 를
# 실패로 끝낸다 (행동 로그 명세 2절 · architecture §5). 키가 만료돼도 max_steps 까지 헛돌지 않게.
MAX_CONSECUTIVE_NO_ACTION = 3

# 같은 화면(elements_hash)의 관측이 이만큼 이어지면 Persona 를 stuck 으로 끝낸다 (GACA-218).
# 같은 화면을 보며 step 상한까지 토큰을 쓰지 않게.
MAX_SAME_SCREEN = 3

# click 해도 요소 줄이 바뀌지 않는 입력칸 — 입력 · 체크 · 선택 상태는 요소 줄에 없다.
# 폼을 보내는 버튼 꼴 input 은 뺀다.
INPUT_TAGS = ("input", "textarea", "select")
BUTTON_INPUT_TYPES = ("submit", "button", "reset", "image")

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


def persona_outcome(history: list[StepResult]) -> Literal["done", "fail", "stuck"] | None:
    """마지막 step 까지 보고 Persona 를 끝낼지 정한다. 더 갈 step 이면 None.

    - "done": done 을 냈다 — Agent 가 스스로 과업 완료를 선언했다 = 성공 (메인 판정 기준, D21).
    - "fail": 행동을 얻지 못한 step 이 MAX_CONSECUTIVE_NO_ACTION 번 이어졌다.
    - "stuck": 같은 화면(elements_hash)의 관측이 MAX_SAME_SCREEN 번 이어졌다 (GACA-218).
      그 마지막 관측의 step 까지 마치고 끝낸다. 관측 사이의 행동을 세는 규칙은
      _counts_same_screen 에 있다.
    """
    last = history[-1].action
    if last is not None and last.kind == "done":
        return "done"
    recent = history[-MAX_CONSECUTIVE_NO_ACTION:]
    if len(recent) == MAX_CONSECUTIVE_NO_ACTION and all(s.action is None for s in recent):
        return "fail"
    recent = history[-MAX_SAME_SCREEN:]
    if (
        len(recent) == MAX_SAME_SCREEN
        and len({elements_hash(s.observation) for s in recent}) == 1
        and all(_counts_same_screen(s) for s in recent[:-1])
    ):
        return "stuck"
    return None


def _counts_same_screen(step: StepResult) -> bool:
    """이 step 의 행동 뒤 관측을 같은 화면으로 세는가. 브라우저에 보낸 click · back 이면 센다.

    아래 행동 뒤에는 세지 않고 처음부터 다시 센다. 세면 Persona 가 잘못 끝난다.
    - scroll: 요소 줄에는 화면 아래 요소도 있어 스크롤해도 같다. 읽으려고 두 번 스크롤하면 끝난다.
    - type · 입력칸 click: 입력값 · 체크 · 선택 상태는 요소 줄에 없다. 아이디 · 비밀번호를 차례로
      넣거나 체크박스 둘을 누르면 끝난다.
    - 행동을 얻지 못한 step: fail 규칙(MAX_CONSECUTIVE_NO_ACTION)이 맡는다.
    - 막힌 행동(step 로그 blocked.is — 도메인 · 파괴적 행동 차단): 막아서 화면이 그대로다. 세면
      가드 켬 조건만 더 자주 끝나 가드 켬 · 끔 A/B test(GACA-180)가 기운다.
    """
    action = step.action
    if action is None or step.result.error_code in BLOCK_REASONS:
        return False
    if action.kind == "back":
        return True
    if action.kind != "click":
        return False
    element = step.observation.element_map.get(action.element_id) or {}
    tag, kind = element.get("tag"), (element.get("type") or "").lower()
    return tag not in INPUT_TAGS or (tag == "input" and kind in BUTTON_INPUT_TYPES)


def elements_hash(observation: Observation) -> str:
    """같은 화면이면 같은 값 — 화면 반복 탐지용. 관측 글(요소 줄) 전체로 만든다."""
    return hashlib.sha256(observation.dom.encode()).hexdigest()[:16]


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
    return {
        "run_id": run_id,
        "persona_id": persona_id,
        "step": step_no,
        "ts": step.finished_at.isoformat(timespec="milliseconds"),
        "url": step.observation.url,
        "observation": {
            "mode": mode,
            "screenshot": screenshot,
            "elements_hash": elements_hash(step.observation),
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
        "task": {"url_reached": same_url(url_after, success_url) if success_url else None},
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
