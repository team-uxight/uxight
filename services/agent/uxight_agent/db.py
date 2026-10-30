import logging

from sqlalchemy import Engine, create_engine, event, make_url

from .config import Settings

logger = logging.getLogger(__name__)

settings = Settings()


def create_db_engine(db_url: str) -> Engine:
    # 동기 DB 호출이 이벤트 루프 안에서 돈다. DB 가 반쯤 끊겨 응답이 없으면 루프 전체
    # (취소 감시 · 시간 상한 · 브라우저)가 멈추므로 PyMySQL 시간 상한(초)으로 끊는다.
    connect_args = {}
    if make_url(db_url).get_backend_name() == "mysql":
        connect_args = {"connect_timeout": 3, "read_timeout": 10, "write_timeout": 10}
    # MySQL 은 오래 쉰 연결을 끊는다(wait_timeout). 쓰기 전에 살아 있는지 보고,
    # 1시간 넘은 연결은 새로 맺는다(10/30 dev 서버에서 'MySQL server has gone away').
    return create_engine(db_url, connect_args=connect_args, pool_pre_ping=True, pool_recycle=3600)


# 앱 전체에서 엔진은 한 번만 생성해서 재사용한다.
engine = create_db_engine(settings.db_url)


@event.listens_for(engine, "after_cursor_execute")
def _log_state_sql(conn, cursor, statement, parameters, context, executemany) -> None:
    # 상태 전이 확인용으로 runs 상태 UPDATE와 run_metrics INSERT만 실행된 SQL 그대로 남긴다.
    # rows=0이면 조건(WHERE status=...)에 막혀 상태가 바뀌지 않았다는 뜻이다.
    # 기록 시점은 커밋 전이다.
    if statement.startswith(("UPDATE runs SET status", "INSERT INTO run_metrics")):
        logger.info("SQL rows=%s | %s | %s", cursor.rowcount, statement, parameters)
