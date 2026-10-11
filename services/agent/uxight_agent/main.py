import logging

from fastapi import FastAPI

from .routers.runs import router as runs_router

# uvicorn은 자체 로거만 설정하므로, 앱 로거(스텝 기록 등)의 INFO 로그가 보이도록 설정한다.
# 취소 소요 시간 등을 로그만으로 확인할 수 있게 밀리초까지 시각을 남긴다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(title="UXight Agent", version="0.0.1")
app.include_router(runs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent"}
