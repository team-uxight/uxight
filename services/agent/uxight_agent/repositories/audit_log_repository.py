import json

from sqlalchemy import text

from ..db import engine

# Spring 감사 로그의 action 이름 규칙(<대상>.<행위>)을 따른다.
BLOCKED_ACTION = "agent.action_blocked"


class AuditLogRepository:
    """audit_log 중 Python 이 쓰는 행(차단된 행동)만 추가한다. 있는 행은 고치지 않는다."""

    def add_blocked_action(self, run_id: int, persona_id: int, detail: dict) -> None:
        # detail 은 반드시 JSON 객체다 — Spring 감사 로그 목록은 객체가 아니면 500 을 낸다.
        if not isinstance(detail, dict):
            raise TypeError("audit detail must be a JSON object")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit_log (actor, action, target, detail) "
                    "VALUES (:actor, :action, :target, :detail)"
                ),
                {
                    "actor": f"agent:{run_id}",
                    "action": BLOCKED_ACTION,
                    "target": f"persona:{persona_id}",
                    "detail": json.dumps(detail, ensure_ascii=False),
                },
            )


audit_log_repository = AuditLogRepository()
