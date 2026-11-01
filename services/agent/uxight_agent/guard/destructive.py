"""파괴적 행동 차단 (GACA-153, agent-safety §2 #3). 되돌릴 수 없는 행동은 마지막 클릭 직전에 막는다.

가장 단순한 규칙으로 고른다. 하나라도 걸리면 클릭하지 않는다.
1. 동사: 요소의 글 · name · 숨은 이름(aria-label · title · 안의 img alt)과 링크 경로 · 폼 action
   에 삭제 · 탈퇴 · 해지 · 결제 · 송금 · 이체 · delete · pay · checkout 같은 행동 동사.
2. 명사: 버튼의 글에 구매 · 주문 · 제출 · 확정 · submit · confirm 같은 말. 다른 쪽으로 가는
   링크에는 걸지 않는다 — '구매입찰' 처럼 메뉴 이름에 흔해서 길 찾기를 막는다.
   페이지를 옮기지 않는 링크(href="#" · javascript:)는 버튼처럼 쓰이므로 버튼으로 본다.
   손가락 커서로 클릭을 받는 칸(링크 · 버튼이 아닌 요소, GACA-225)도 버튼으로 본다.
3. 속성: POST 폼을 보내는 제출 버튼 — 서버에 무언가를 써 넣는 전송이다. 글이 검색 · 조회 ·
   search 인 버튼은 뺀다 (게시판 검색 폼이 POST 인 사이트가 흔하다).

한계: 스크립트로 하는 제출(<a href="#" onclick="form.submit()">확인</a>) · onclick 의 fetch 는
요소만 보고는 알 수 없어 1 · 2 의 글에 걸리지 않으면 막지 못한다. POST 폼 안의 '#' 링크를 모두
막으면 게시판 쪽 번호 링크(학교 사본 228개)까지 막혀서 넣지 않았다. 도메인 가드가 허용 밖 이동만은
막는다.
"""

import re
import unicodedata
from urllib.parse import unquote, urlsplit

from ..driver.base import Observation
from ..schemas import Action

# 한국어는 띄어 써도 걸리게 공백을 지운 글에서 찾는다 ('회원 탈퇴', '결 제').
KOREAN_VERBS = ("삭제", "탈퇴", "해지", "결제", "송금", "이체")
KOREAN_NOUNS = ("구매", "주문", "제출", "확정")
ENGLISH_VERBS = re.compile(
    r"\b(?:delete|remove|withdraw|unsubscribe|deactivate|close account|"
    r"cancel (?:subscription|membership|account)|pay|payment|checkout|check out|"
    r"transfer|send money)\b",
    re.IGNORECASE,
)
ENGLISH_NOUNS = re.compile(
    r"\b(?:purchase|buy|place order|order now|submit|confirm)\b", re.IGNORECASE
)
SEARCH_WORDS = re.compile(r"검색|조회|\bsearch\b|\bfind\b", re.IGNORECASE)
BUTTON_TAGS = ("button", "input")


def destructive_reason(action: Action, observation: Observation) -> str | None:
    """click 할 요소가 파괴적 행동이면 그 까닭(짧은 영어), 아니면 None."""
    if action.kind != "click":
        return None
    element = observation.element_map.get(action.element_id) or {}
    label = _normalize(
        " ".join(filter(None, (element.get("text"), element.get("name"), element.get("hint"))))
    )
    is_button = _acts_like_button(element, observation.url)
    if word := _find_word(label, KOREAN_VERBS, ENGLISH_VERBS):
        return f"keyword '{word}'"
    if is_button and (word := _find_word(label, KOREAN_NOUNS, ENGLISH_NOUNS)):
        return f"keyword '{word}'"
    # 링크 목적지 · 폼 action 경로의 동사 (/member/delete.do 등)
    for url in (element.get("url"), element.get("form_action")):
        if url and (reason := destructive_path(url)):
            return reason
    if (
        element.get("form_method") == "post"
        and _is_submit(element)
        and not SEARCH_WORDS.search(label)
    ):
        return "submit of a POST form"
    return None


def destructive_path(url: str) -> str | None:
    """주소의 경로 · 쿼리 이름에 행동 동사가 있으면 그 까닭, 아니면 None (/member/delete.do 등).

    요소의 링크 목적지 · 폼 action 과, 새 창 대신 주 창에서 열 주소(GACA-225)에 쓴다.
    """
    word = _find_word(_path_words(url), KOREAN_VERBS, ENGLISH_VERBS)
    return f"path '{word}'" if word else None


def _acts_like_button(element: dict, page_url: str) -> bool:
    if element.get("tag") in BUTTON_TAGS or element.get("role") == "button":
        return True
    if element.get("pointer"):  # 손가락 커서로 클릭을 받는 칸 (GACA-225)
        return True
    url = element.get("url") or ""
    return url.startswith("javascript:") or (
        bool(url) and url.split("#")[0] == page_url.split("#")[0]
    )


def _find_word(text: str, korean: tuple[str, ...], english: re.Pattern[str]) -> str | None:
    compact = re.sub(r"\s+", "", text)
    for word in korean:
        if word in compact:
            return word
    match = english.search(text)
    return match.group().lower() if match else None


def _path_words(url: str) -> str:
    # 경로 · 쿼리 이름의 구분 글자(/ . _ - = & ?)를 공백으로 — 'member_delete.do' 의 delete 를 찾게.
    parts = urlsplit(url)
    return _normalize(re.sub(r"[/._\-=&?]+", " ", unquote(f"{parts.path} {parts.query}")))


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
