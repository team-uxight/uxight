from sqlalchemy import text

from ..db import engine


class RunPersonaRepository:
    """run_personas 테이블 데이터 접근 계층. 전 컬럼 Python 소유([P])."""

    def create_for_persona(self, run_id: int, log_paths: dict[int, str]) -> None:
        # log_paths: persona_id → 로그 루트 기준 상대 경로. 페르소나마다 파일이 따로 있다.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO run_personas "
                    "(run_id, persona_id, status, steps, log_path, started_at) "
                    "VALUES (:run_id, :persona_id, 'running', 0, :log_path, NOW())"
                ),
                [
                    {"run_id": run_id, "persona_id": persona_id, "log_path": log_path}
                    for persona_id, log_path in log_paths.items()
                ],
            )

    def get_statuses(self, run_id: int) -> dict[int, str]:
        # 런에 속한 페르소나별 상태 (persona_id → status).
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT persona_id, status FROM run_personas WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            return {persona_id: status for persona_id, status in rows}

    def increment_steps(self, run_id: int, persona_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas SET steps = steps + 1 "
                    "WHERE run_id = :run_id AND persona_id = :persona_id AND status = 'running'"
                ),
                {"run_id": run_id, "persona_id": persona_id},
            )

    def mark_completed(self, run_id: int, persona_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas SET status = 'completed', finished_at = NOW() "
                    "WHERE run_id = :run_id AND persona_id = :persona_id AND status = 'running'"
                ),
                {"run_id": run_id, "persona_id": persona_id},
            )

    def mark_failed(self, run_id: int, persona_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas SET status = 'fail', finished_at = NOW() "
                    "WHERE run_id = :run_id AND persona_id = :persona_id AND status = 'running'"
                ),
                {"run_id": run_id, "persona_id": persona_id},
            )

    def mark_cancelled(self, run_id: int, persona_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas SET status = 'cancelled', finished_at = NOW() "
                    "WHERE run_id = :run_id AND persona_id = :persona_id AND status = 'running'"
                ),
                {"run_id": run_id, "persona_id": persona_id},
            )


run_persona_repository = RunPersonaRepository()
