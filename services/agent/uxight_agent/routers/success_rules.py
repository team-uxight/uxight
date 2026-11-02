import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError
from pydantic import BaseModel

from ..llm import LLMClient
from ..success_rule import MAX_RETRIES, SuccessRuleError, create_success_rule

logger = logging.getLogger(__name__)

router = APIRouter()


class SuccessRuleRequest(BaseModel):
    """내부 API 0 요청 본문. 내부 API JSON 은 snake_case."""

    target_url: str
    goal: str
    success_url: str


class SuccessRuleResponse(BaseModel):
    success_rule: str


def get_llm() -> LLMClient:
    """요청마다 env(LLM_BASE_URL · LLM_API_KEY · LLM_MODEL)로 만든다. 테스트는 가짜로 바꾼다."""
    return LLMClient(max_retries=MAX_RETRIES)


@router.post("/success-rules")
async def create(
    payload: SuccessRuleRequest, llm: Annotated[LLMClient, Depends(get_llm)]
) -> SuccessRuleResponse:
    # DB 에 쓰지 않고 만든 문장만 돌려준다 — 저장은 Spring 이 해서 201 이 아니라 200 이다.
    # 로그에는 목표 문장 · 생성된 문장을 남기지 않는다.
    start = time.monotonic()
    try:
        rule = await create_success_rule(llm, payload.target_url, payload.goal, payload.success_url)
    except (APIError, SuccessRuleError) as e:
        # APITimeoutError 도 APIError 다. Spring 은 실패 응답을 502(EXP-ERR-007)로 바꾼다.
        logger.warning("POST /success-rules → 502 (%s) %dms", type(e).__name__, _ms(start))
        raise HTTPException(status_code=502, detail="success rule generation failed") from e
    logger.info("POST /success-rules → 200 %dms", _ms(start))
    return SuccessRuleResponse(success_rule=rule)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
