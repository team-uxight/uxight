"""페이지 글의 지시문 패턴 표시 (관측 정제 L0.5, agent-safety §2.2 #4).

페이지 글은 신뢰하지 않는 입력이다. 모델에게 내리는 지시처럼 보이는 문구를 찾아 표시만 하고
지우지는 않는다 — 정상 글("You are now logged in" 등)도 걸릴 수 있어서 판단 재료를 남긴다.
표시한 글을 인용 블록으로 감싸 프롬프트에 넣는 일은 프롬프트 빌더(GACA-107) 몫이다.
"""

import re
import unicodedata

# 걸린 부분을 감싸는 표시.
MARK_START = "[[지시문 의심: "
MARK_END = "]]"

# 이름 → 패턴(영어 | 한국어). 걸린 패턴은 이름으로 돌려준다.
# [^.?!\n] 는 한 문장 안에서만 찾게 해 "Forget your password? Read the rules" 같은 오탐을 줄인다.
INSTRUCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "ignore_previous": re.compile(
        r"\b(?:ignore|disregard|forget|override)\b[^.?!\n]{0,30}?"
        r"\b(?:instructions?|prompts?|rules?|guidelines?|above)\b"
        r"|(?:이전|앞|위|기존|모든|지금까지)[^.?!\n]{0,10}?(?:지시|명령|지침|프롬프트|규칙)"
        r"[^.?!\n]{0,10}?(?:무시|잊)",
        re.IGNORECASE,
    ),
    # 줄 머리나 따옴표 · 괄호 · 본문 표 칸 구분("| ") 바로 뒤의 "system:" — 대화 역할을 사칭한다.
    # 문장 중간("Operating system: macOS")은 정상 글이 많아 뺀다.
    "role_prefix": re.compile(
        r"(?:^|(?<=[\"'\[(<{])|(?<=\| ))(?:system|assistant|developer|시스템)\s*:",
        re.IGNORECASE | re.MULTILINE,
    ),
    "you_are_now": re.compile(r"\byou\s+are\s+now\b|(?:너는|넌|당신은)\s*이제", re.IGNORECASE),
    "new_instructions": re.compile(
        r"\b(?:new|updated)\s+instructions?\b|새로운?\s*(?:지시|명령|지침)", re.IGNORECASE
    ),
    "system_prompt": re.compile(r"\bsystem\s+prompt\b|시스템\s*프롬프트", re.IGNORECASE),
}


def mark_instructions(text: str) -> tuple[str, list[str]]:
    """페이지 글에서 지시문 패턴을 찾아 (표시한 글, 걸린 패턴 이름 목록)을 돌려준다.

    걸린 부분만 MARK_START · MARK_END 로 감싸고 원문 글자는 그대로 둔다. 안 걸리면 (원문, []).
    패턴은 원문이 아니라 다듬은 글(_search_text)에서 찾는다.
    - 전각 · 호환 문자는 NFKC 로 바꾼다 ("시스템：" → "시스템:").
    - 제로폭 · soft hyphen · 방향 제어 같은 보이지 않는 서식 문자(Cf)는 지운다.
    원문의 [[ · ]] 는 하나로 줄여 표시를 흉내 내지 못하게 한다 (collapse_marks).
    그래서 이미 표시한 글에 다시 쓰면 표시가 망가진다 — 원문에 한 번만 쓴다.
    """
    text = collapse_marks(text)
    search, origin = _search_text(text)

    spans: list[tuple[int, int]] = []
    hits: list[str] = []
    for name, pattern in INSTRUCTION_PATTERNS.items():
        found = [
            (origin[match.start()][0], origin[match.end() - 1][1])
            for match in pattern.finditer(search)
            if match.group()  # 빈 매치는 감쌀 글이 없다.
        ]
        if found:
            hits.append(name)
            spans += found

    # 겹치거나 맞닿은 구간은 합쳐서 한 번만 감싼다.
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    parts: list[str] = []
    last = 0
    for start, end in merged:
        parts += [text[last:start], MARK_START, text[start:end], MARK_END]
        last = end
    parts.append(text[last:])
    return "".join(parts), hits


def collapse_marks(text: str) -> str:
    """[[ · ]] 처럼 이어진 같은 괄호를 하나로 줄인다.

    찾기용 글과 같은 기준으로 괄호를 본다 — 전각 괄호("［")도 괄호이고, 괄호 사이에 낀
    서식 문자("[\u200b[")는 없는 글자로 보고 함께 지운다.
    지시문 표시를 붙이지 않는 그림자 모드(GACA-180)의 프롬프트도 이것은 쓴다.
    """
    kept: list[str] = []
    bracket = ""  # 마지막으로 남긴 괄호 (그 뒤로 서식 문자만 왔을 때)
    between: list[str] = []  # 그 괄호 뒤에 온 서식 문자
    for char in text:
        normalized = _normalize(char)
        if bracket and normalized == bracket:
            between = []
        elif bracket and not normalized:
            between.append(char)
        else:
            kept += [*between, char]
            between = []
            bracket = normalized if normalized in ("[", "]") else ""
    return "".join(kept + between)


def _normalize(text: str) -> str:
    """NFKC 로 바꾸고 서식 문자(Cf)를 지운다."""
    return "".join(
        c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf"
    )


def _search_text(text: str) -> tuple[str, list[tuple[int, int]]]:
    """패턴을 찾을 다듬은 글과, 그 글자마다 원문 범위 (시작, 끝)를 돌려준다.

    보통은 글자 하나씩 다듬어 원문 글자 위치를 그대로 잇는다. 첫가끝 자모 · 결합 문자처럼
    NFKC 가 앞뒤 글자를 합치는 낱말(공백 사이 조각)은 글자 하나씩 다듬으면 결과가 달라지므로
    낱말째 다듬고 낱말 전체를 원문 범위로 삼는다 — 그래서 표시가 낱말 끝까지 넓어질 수 있다.
    NFKC 는 공백을 넘어 글자를 합치지 않으므로 낱말마다 다듬어 이은 글은 통째로 다듬은 글과 같다.
    """
    search: list[str] = []
    origin: list[tuple[int, int]] = []
    for word in re.finditer(r"\s+|\S+", text):
        whole = _normalize(word.group())
        each = [_normalize(char) for char in word.group()]
        if "".join(each) == whole:
            for index, normalized in enumerate(each, word.start()):
                origin += [(index, index + 1)] * len(normalized)
        else:
            origin += [word.span()] * len(whole)
        search.append(whole)
    return "".join(search), origin
