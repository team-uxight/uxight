import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from ..repositories.run_repository import run_repository
from ..schemas import RunRequest
from ..watcher.run_orchestrator import run_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/runs")
def create_run(payload: RunRequest, background_tasks: BackgroundTasks) -> JSONResponse:
    snapshot = run_orchestrator.try_accept_and_start(payload.run_id)
    if snapshot is None:
        # queued 가 아니다 — 이미 받은 회차(멱등 200)거나 없는 회차(404).
        status = run_repository.get_status(payload.run_id)
        if status is None:
            logger.info("POST /runs run_id=%s → 404 (회차 없음)", payload.run_id)
            raise HTTPException(status_code=404, detail="run not found")
        body = {"run_id": payload.run_id, "status": status}
        logger.info("POST /runs run_id=%s → 200 (중복 요청) %s", payload.run_id, body)
        return JSONResponse(status_code=200, content=body)

    background_tasks.add_task(run_orchestrator.run_personas, payload.run_id, snapshot)
    logger.info("POST /runs run_id=%s → 202 %s", payload.run_id, {"run_id": payload.run_id})
    return JSONResponse(status_code=202, content={"run_id": payload.run_id})
