import logging

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from ..schemas import RunRequest
from ..watcher.run_orchestrator import run_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/runs")
def create_run(payload: RunRequest, background_tasks: BackgroundTasks) -> JSONResponse:
    persona_ids = [persona["persona_id"] for persona in payload.persona_snapshot]

    accepted = run_orchestrator.try_accept_and_start(payload.run_id, persona_ids)
    if not accepted:
        # 이미 accepted 처리된 중복 요청 - 같은 본문으로 200 응답 (멱등).
        logger.info(
            "POST /runs run_id=%s → 200 (중복 요청) %s", payload.run_id, {"run_id": payload.run_id}
        )
        return JSONResponse(status_code=200, content={"run_id": payload.run_id})

    max_steps = payload.policy_snapshot["max_steps"]
    background_tasks.add_task(
        run_orchestrator.run_personas,
        payload.run_id,
        payload.task_snapshot,
        payload.persona_snapshot,
        max_steps,
    )
    logger.info("POST /runs run_id=%s → 202 %s", payload.run_id, {"run_id": payload.run_id})
    return JSONResponse(status_code=202, content={"run_id": payload.run_id})
