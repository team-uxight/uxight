import json
from pathlib import Path

from ..db import settings

LOG_FILE_NAME = "steps.jsonl"


class StepLogWriter:
    """페르소나 단위 스텝 로그 파일(<log_dir>/<run_id>/<persona_id>/steps.jsonl)을 쓴다.

    쓰기 주체는 AI Orchestrator뿐이다.
    """

    def __init__(self, log_dir: str) -> None:
        self._root = Path(log_dir)

    def relative_path(self, run_id: int, persona_id: int) -> str:
        # run_personas.log_path에 저장하는 값. Spring은 자신의 마운트 위치에 이 경로를 붙여 읽는다.
        return f"{run_id}/{persona_id}/{LOG_FILE_NAME}"

    def prepare(self, run_id: int, persona_id: int) -> None:
        path = self._root / self.relative_path(run_id, persona_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

    def append(self, run_id: int, persona_id: int, record: dict) -> None:
        # 한 줄 = 한 스텝. 모든 페르소나가 한 이벤트 루프에서 동기로 한 줄씩 쓰므로
        # 줄이 섞이지 않는다.
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(self._root / self.relative_path(run_id, persona_id), "a", encoding="utf-8") as f:
            f.write(line + "\n")


step_log_writer = StepLogWriter(settings.log_dir)
