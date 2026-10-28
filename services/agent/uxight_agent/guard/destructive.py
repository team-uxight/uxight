"""파괴적 행동 차단 (GACA-153, agent-safety §2 #3). 되돌릴 수 없는 행동은 마지막 클릭 직전에 막는다.

가장 단순한 규칙 두 가지로 고른다. 하나라도 걸리면 클릭하지 않는다.
1. 낱말: 누를 요소의 글 · name 에 삭제 · 탈퇴 · 결제 · 구매 · 송금 · 해지 · 제출 확정 같은 낱말.
   링크 · 버튼을 가리지 않는다 — 메뉴 링크 '결제 안내' 도 막힌다 (더 안전한 쪽).
2. 속성: POST 폼을 보내는 제출 버튼 — 글과 상관없이 서버에 무언가를 써 넣는 전송이다.
"""

import re
import unicodedata

from ..driver.base import Observation
from ..schemas import Action

# 한국어는 띄어 써도 걸리게 공백을 지운 글에서 찾는다 ('회원 탈퇴', '결 제').
KOREAN_WORDS = ("삭제", "탈퇴", "해지", "결제", "구매", "주문", "송금", "이체", "제출", "확정")
ENGLISH_WORDS = re.compile(
    r"\b(?:delete|remove|unsubscribe|deactivate|cancel (?:subscription|membership|account)|"
    r"close account|pay|payment|purchase|buy|checkout|check out|place order|order now|"
    r"transfer|send money|submit|confirm)\b",
    re.IGNORECASE,
)


def destructive_reason(action: Action, observation: Observation) -> str | None:
    """click 할 요소가 파괴적 행동이면 그 까닭(짧은 영어), 아니면 None."""
    if action.kind != "click":
        return None
    element = observation.element_map.get(action.element_id) or {}
    label = _normalize(" ".join(filter(None, (element.get("text"), element.get("name")))))
    compact = re.sub(r"\s+", "", label)
    for word in KOREAN_WORDS:
        if word in compact:
            return f"keyword '{word}'"
    if match := ENGLISH_WORDS.search(label):
        return f"keyword '{match.group().lower()}'"
    if element.get("form_method") == "post" and _is_submit(element):
        return "submit of a POST form"
    return None


def _is_submit(element: dict) -> bool:
    kind = (element.get("type") or "").lower()
    if element.get("tag") == "button":
        return kind in ("", "submit")  # 폼 안 button 의 기본 type 은 submit
    return element.get("tag") == "input" and kind in ("submit", "image")


def _normalize(text: str) -> str:
    # 전각 · 호환 글자를 바꾸고 보이지 않는 서식 문자(제로폭 등)를 지운다 (지시문 표시와 같은 기준).
    return "".join(
        c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf"
    )
