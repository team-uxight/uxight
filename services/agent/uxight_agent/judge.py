"""성공 판정 보조 (GACA-161). 규칙이 도달 여부를 내지 못한 Persona 만 판정 LLM 이 채운다.

- 규칙(step 로그의 url_reached)이 True · False 를 낸 Persona 는 판정하지 않는다.
  빈칸(None)만 채운다.
- 프롬프트 · 답 모양 · 입력 칸은 bakeoff 의 판정(문제집 eval/cases/judge.jsonl)과 같다.
  가상 사용자의 '찾았다'는 믿지 않고 마지막 화면만 본다.
- 입력 내용은 문제집과 조금 다르다. 마지막 행동의 대상은 요소 번호('click [12]')이고 문제집은
  요소 글('click [학사안내]')이다. 본문 글은 링크 · 버튼 글이 빠진 화면 안 글이고 2000자까지다.
  경로(crumb)는 빈 목록이다. 그래서 문제집 일치율이 실제 판정에 그대로 옮겨지지는 않는다.
- 판정 답은 run_personas.url_reached 에만 들어간다. 진단 · Friction 규칙은 step 로그의
  url_reached 를 보므로, 판정한 Persona 도 거기서는 판정 안 함으로 남는다.
"""

from typing import Any

from .bakeoff import SYSTEM, Judgment, user_message
from .driver.base import Observation
from .llm import LLMClient

ROLE = "judge"
MAX_TOKENS = 2000  # bakeoff 와 같은 한도. 추론 모델은 생각 토큰도 여기에 든다
# 호출 하나의 상한(초)과 재시도. Persona 자리를 돌려준 뒤에 부르므로 브라우저를 붙잡지 않는다.
TIMEOUT_SECONDS = 60
MAX_RETRIES = 1
TEXT_CHARS = 2000  # 마지막 화면 본문 글은 앞에서 이만큼만 넣는다
LAST_ACTIONS = 5


def judge_input(task: dict, steps: list[dict], page: Observation | None) -> dict | None:
    """판정 LLM 에 줄 입력. 문제집의 input(task · criterion · final_page · last_actions) 모양이다.

    마지막 화면은 Persona 가 끝날 때 본 화면(page)이다. step 로그에는 제목 · 본문 글이 없어서다.
    경로(crumb)는 관측에 없어 빈 목록이다. 마지막 행동은 step 로그에서 뽑는다.
    page 가 없으면(첫 화면도 보지 못하고 끝남) 판정할 것이 없어 None 이다.
    """
    if page is None:
        return None
    return {
        "task": task.get("goal") or "",
        "criterion": task.get("success_rule") or "",
        "final_page": {
            "url": page.url,
            "title": page.title,
            "crumb": [],
            "text": page.text[:TEXT_CHARS],
        },
        "last_actions": last_actions(steps),
    }


def last_actions(steps: list[dict]) -> list[str]:
    """행동이 있는 step 의 마지막 몇 개. done 은 그 step 의 이유(reasoning)를 붙인다."""
    out = []
    for record in steps:
        action = record.get("action")
        if action is None:
            continue  # 행동을 얻지 못한 step
        kind = action["kind"]
        if kind in ("click", "type"):
            out.append(f"{kind} [{action['target']}]")  # type 의 입력값은 로그에도 없다
        elif kind == "scroll":
            out.append(f"scroll {action['direction']}")
        elif kind == "done" and record.get("reasoning"):
            out.append(f"done — {record['reasoning']}")
        else:
            out.append(kind)
    return out[-LAST_ACTIONS:]


async def judge(
    llm: LLMClient, payload: dict[str, Any], *, run_id: int, persona_id: int
) -> Judgment:
    """판정 LLM 을 한 번 부른다. 호출 실패는 예외 그대로, 형식이 틀린 답은 ValueError 다."""
    response = await llm.chat(
        [
            {"role": "system", "content": SYSTEM["judge"]},
            {"role": "user", "content": user_message("judge", payload)},
        ],
        role=ROLE,
        max_tokens=MAX_TOKENS,
        response_format=Judgment,
        run_id=run_id,
        persona_id=str(persona_id),
        timeout=TIMEOUT_SECONDS,
    )
    parsed = response.choices[0].message.parsed if response.choices else None
    if parsed is None:
        raise ValueError("판정 답의 형식이 맞지 않음")
    return parsed
