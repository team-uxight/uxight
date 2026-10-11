import logging

from sqlalchemy import create_engine, event

from .config import Settings

logger = logging.getLogger(__name__)

settings = Settings()
# 앱 전체에서 엔진은 한 번만 생성해서 재사용한다.
engine = create_engine(settings.db_url)


@event.listens_for(engine, "after_cursor_execute")
def _log_state_sql(conn, cursor, statement, parameters, context, executemany) -> None:
    # 상태 전이 확인용으로 runs 상태 UPDATE와 run_metrics INSERT만 실행된 SQL 그대로 남긴다.
    # rows=0이면 조건(WHERE status=...)에 막혀 상태가 바뀌지 않았다는 뜻이다.
    # 기록 시점은 커밋 전이다.
    if statement.startswith(("UPDATE runs SET status", "INSERT INTO run_metrics")):
        logger.info("SQL rows=%s | %s | %s", cursor.rowcount, statement, parameters)
