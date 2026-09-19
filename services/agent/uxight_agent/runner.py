"""실행 골격. 지금은 로그만 남긴다.

Persona Agent 루프(관측 → LLM → 검증 → 실행)는 S2 에서 여기에 들어온다.
"""

import logging

from .schemas import RunRequest

log = logging.getLogger(__name__)

MAX_STEPS = 20  # agent-safety §2.2 #5 — 실행당 step 상한


async def run(req: RunRequest) -> None:
    """한 run 을 끝까지 돌린다. 상태(RUNNING → DONE | FAILED)는 MySQL runs 행에 쓴다 (S2)."""
    log.info("run %s start target=%s task=%r", req.run_id, req.target_url, req.task)
    # TODO(S2): Playwright context → observe/act 루프 (step ≤ MAX_STEPS)
    #           → 행동 로그 JSON(data/) → runs.status 갱신
    log.info("run %s done (stub)", req.run_id)
