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
    # 줄 머리나 따옴표 · 괄호 바로 뒤의 "system:" — 대화 역할을 사칭한다.
    # 문장 중간("Operating system: macOS")은 정상 글이 많아 뺀다.
    "role_prefix": re.compile(
        r"(?:^|(?<=[\"'\[(<{]))(?:system|assistant|developer|시스템)\s*:",
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

    걸린 부분만 MARK_START · MARK_END 로 감싸고 나머지는 그대로 둔다. 안 걸리면 (원문, []).
    찾기 전에 글을 다듬고, 돌려주는 글도 다듬은 글이다.
    - 전각 · 호환 문자는 NFKC 로 바꾼다 ("시스템：" → "시스템:"). "①" → "1" 처럼 글이 바뀔 수 있다.
    - 제로폭 · soft hyphen · 방향 제어 같은 보이지 않는 서식 문자(Cf)는 지운다.
    - 원문의 [[ · ]] 는 하나로 줄여 표시를 흉내 내지 못하게 한다.
      그래서 이미 표시한 글에 다시 쓰면 표시가 망가진다 — 원문에 한 번만 쓴다.
    """
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    text = re.sub(r"\]\]+", "]", re.sub(r"\[\[+", "[", text))

    spans: list[tuple[int, int]] = []
    hits: list[str] = []
    for name, pattern in INSTRUCTION_PATTERNS.items():
        found = [match.span() for match in pattern.finditer(text)]
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
