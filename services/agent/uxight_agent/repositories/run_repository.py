import json
from dataclasses import dataclass

from sqlalchemy import text

from ..db import engine


@dataclass(frozen=True)
class RunSnapshot:
    """Spring 이 회차 INSERT 때 남긴 [S] 스냅샷. 한 실험의 회차는 모두 같은 스냅샷으로 실행한다."""

    target_url: str
    allowed_domains: list[str]  # 가드 허용 도메인. 아직 읽기만 한다 (guard 미구현)
    task: dict  # task_id, goal, success_rule, success_url, is_one_shot
    personas: list[dict]  # [{persona_id, name, profile}]
    policy: dict  # max_steps, ...


class RunRepository:
    """runs 테이블 중 Python이 소유하는 컬럼([P])만 다룬다."""

    def accept_if_queued(self, run_id: int) -> bool:
        # status가 'queued'일 때만 'accepted'로 전이한다.
        # 영향 행 수가 0이면 이미 수락 처리된 중복 요청이라는 뜻.
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE runs SET status = 'accepted', accepted_at = NOW() "
                    "WHERE run_id = :run_id AND status = 'queued'"
                ),
                {"run_id": run_id},
            )
            return result.rowcount == 1

    def mark_running(self, run_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE runs SET status = 'running', started_at = NOW() "
                    "WHERE run_id = :run_id AND status = 'accepted'"
                ),
                {"run_id": run_id},
            )

    def mark_done(self, run_id: int, success_rate: float) -> None:
        # runs.status='done' UPDATE와 run_metrics INSERT는 한 트랜잭션으로 묶는다.
        # 상태가 실제로 바뀐 경우에만 INSERT해서 회차 당 1행을 보장한다.
        # Walking Skeleton에서는 avg_*, tokens, cost_usd를 채우지 않는다(NULL).
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE runs SET status = 'done', finished_at = NOW() "
                    "WHERE run_id = :run_id AND status = 'running'"
                ),
                {"run_id": run_id},
            )
            if result.rowcount == 1:
                conn.execute(
                    text(
                        "INSERT INTO run_metrics (run_id, success_rate) "
                        "VALUES (:run_id, :success_rate)"
                    ),
                    {"run_id": run_id, "success_rate": success_rate},
                )

    def mark_failed(self, run_id: int, error: str) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE runs SET status = 'failed', error = :error, finished_at = NOW() "
                    "WHERE run_id = :run_id AND status = 'running'"
                ),
                {"run_id": run_id, "error": error},
            )

    def mark_cancelled(self, run_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE runs SET status = 'cancelled', finished_at = NOW() "
                    "WHERE run_id = :run_id AND status = 'running'"
                ),
                {"run_id": run_id},
            )

    def get_status(self, run_id: int) -> str | None:
        # 회차가 없으면 None.
        with engine.begin() as conn:
            return conn.execute(
                text("SELECT status FROM runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one_or_none()

    def get_snapshot(self, run_id: int) -> RunSnapshot:
        # JSON 컬럼은 PyMySQL 이 문자열로 돌려준다.
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT target_url_snapshot, allowed_domains_snapshot, task_snapshot, "
                    "persona_snapshot, policy_snapshot "
                    "FROM runs WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).one()
        return RunSnapshot(
            target_url=row.target_url_snapshot,
            allowed_domains=json.loads(row.allowed_domains_snapshot),
            task=json.loads(row.task_snapshot),
            personas=json.loads(row.persona_snapshot),
            policy=json.loads(row.policy_snapshot),
        )

    def refresh_progress(self, run_id: int) -> None:
        # progress = 정상 종료된(done/max_steps) 페르소나 수. fail/timeout/cancelled는 세지 않는다.
        # +1 대신 매번 다시 세어 덮어쓰므로 중복 호출이나 동시 완료에도 값이 정확하다.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE runs SET progress = ("
                    "  SELECT COUNT(*) FROM run_personas "
                    "  WHERE run_id = :run_id AND status IN ('done', 'max_steps')"
                    ") WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            )

    def is_cancel_requested(self, run_id: int) -> bool:
        with engine.begin() as conn:
            return conn.execute(
                text("SELECT cancel_requested FROM runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()


run_repository = RunRepository()
