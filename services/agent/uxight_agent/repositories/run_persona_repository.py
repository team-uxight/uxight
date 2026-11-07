from typing import Literal

from sqlalchemy import text

from ..db import engine

# running 이 아닌 종료 상태.
# done = Agent 가 스스로 done 을 냄(성공, 메인 판정 기준), max_steps = 스텝 소진,
# token_limit = 토큰 상한 · 하루 예산, stuck = 같은 화면이 이어짐 (GACA-218 · V9 마이그레이션).
PersonaOutcome = Literal[
    "done", "max_steps", "token_limit", "stuck", "fail", "timeout", "cancelled"
]

# step 비용을 누적 비용 칸(cost_usd)에 더하는 SET 절. :cost_usd 가 NULL 이면 칸을 그대로 둔다.
_ADD_COST = (
    "cost_usd = CASE WHEN :cost_usd IS NULL THEN cost_usd "
    "ELSE COALESCE(cost_usd, 0) + :cost_usd END"
)


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

    def mark_started(self, run_id: int, persona_id: int) -> None:
        """실행 슬롯을 확보한 시점부터 Persona 실행 시간을 측정한다."""
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas SET started_at = NOW() "
                    "WHERE run_id = :run_id AND persona_id = :persona_id "
                    "AND status = 'running'"
                ),
                {"run_id": run_id, "persona_id": persona_id},
            )

    def get_statuses(self, run_id: int) -> dict[int, str]:
        # 회차에 속한 페르소나별 상태 (persona_id → status).
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT persona_id, status FROM run_personas WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            return {persona_id: status for persona_id, status in rows}

    def get_outcomes(self, run_id: int) -> dict[int, tuple[str, bool | None]]:
        """Persona별 종료 상태와 성공 URL 도달 여부를 함께 조회한다."""
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT persona_id, status, url_reached "
                    "FROM run_personas WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            )
            return {
                persona_id: (status, None if url_reached is None else bool(url_reached))
                for persona_id, status, url_reached in rows
            }

    def increment_steps(
        self, run_id: int, persona_id: int, tokens: int = 0, cost_usd: float | None = None
    ) -> None:
        # step 하나를 센다. 그 step 의 LLM 토큰과 비용은 Persona 와 회차 누적에 같이 더한다 —
        # runs.tokens 의 당일 합계가 하루 예산 집행의 기준이다 (V4__policies.sql).
        # cost_usd 가 None 이면(단가 없는 모델) 토큰만 더하고 비용 칸은 그대로 둔다.
        params = {
            "run_id": run_id,
            "persona_id": persona_id,
            "tokens": tokens,
            "cost_usd": cost_usd,
        }
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas SET steps = steps + 1, "
                    "tokens = COALESCE(tokens, 0) + :tokens, "
                    f"{_ADD_COST} "
                    "WHERE run_id = :run_id AND persona_id = :persona_id AND status = 'running'"
                ),
                params,
            )
            conn.execute(
                text(
                    "UPDATE runs SET tokens = COALESCE(tokens, 0) + :tokens, "
                    f"{_ADD_COST} WHERE run_id = :run_id"
                ),
                params,
            )

    def mark_finished(
        self,
        run_id: int,
        persona_id: int,
        status: PersonaOutcome,
        url_reached: bool | None = None,
    ) -> None:
        # 이미 종료된 Persona는 덮어쓰지 않는다.
        # URL 도달 여부는 전체 Step 로그를 기준으로 집계한 값이다.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE run_personas "
                    "SET status = :status, url_reached = :url_reached, finished_at = NOW() "
                    "WHERE run_id = :run_id AND persona_id = :persona_id AND status = 'running'"
                ),
                {
                    "run_id": run_id,
                    "persona_id": persona_id,
                    "status": status,
                    "url_reached": url_reached,
                },
            )


run_persona_repository = RunPersonaRepository()
