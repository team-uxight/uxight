import logging

from fastapi import BackgroundTasks, FastAPI, status

from . import runner
from .schemas import RunRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="UXight Agent", version="0.0.1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent"}


@app.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(req: RunRequest, background: BackgroundTasks) -> dict[str, int | str]:
    """api 가 부르는 유일한 엔드포인트. 바로 202 를 돌려주고 실행은 백그라운드에서."""
    background.add_task(runner.run, req)
    return {"run_id": req.run_id, "status": "ACCEPTED"}


def main() -> None:  # `uv run uxight-agent`
    import uvicorn

    uvicorn.run("uxight_agent.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
