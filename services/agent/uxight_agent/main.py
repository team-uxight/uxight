import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routers.runs import router as runs_router
from .watcher.run_orchestrator import run_orchestrator

# uvicorn은 자체 로거만 설정하므로, 앱 로거(스텝 기록 등)의 INFO 로그가 보이도록 설정한다.
# 취소 소요 시간 등을 로그만으로 확인할 수 있게 밀리초까지 시각을 남긴다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 시작 시 한 번: 이전 프로세스가 accepted · running 으로 남긴 회차를 정리한다
    # (architecture §3.3).
    try:
        run_orchestrator.close_interrupted_runs()
    except Exception:
        # DB 에 닿지 못해도 기동은 계속한다. 남은 회차는 다음 기동 때 정리된다.
        logger.exception("closing interrupted runs failed")
    yield


app = FastAPI(title="UXight Agent", version="0.0.1", lifespan=lifespan)
app.include_router(runs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent"}
