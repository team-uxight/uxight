"""runs 상태 SQL (GACA-110 리뷰). CI 에는 MySQL 이 없다.

SQLite 파일 DB 에 실제 SQL 을 돌리고, MySQL 함수 NOW() 만 흉내 낸다.
"""

from pathlib import Path

import pytest
from sqlalchemy import Engine, event, text

from uxight_agent.db import create_db_engine
from uxight_agent.repositories import run_repository as repository_module
from uxight_agent.repositories.run_repository import RunRepository

NOW = "2026-10-21 12:00:00"


def sqlite_engine(tmp_path: Path) -> Engine:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'agent.db'}")

    @event.listens_for(engine, "connect")
    def add_now(dbapi_conn, conn_rec) -> None:
        dbapi_conn.create_function("NOW", 0, lambda: NOW)

    return engine


def test_mark_running_writes_heartbeat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Spring 의 멈춤(stale) 표시는 heartbeat_at 이 NULL 이면 뜨지 않는다. running 이 되는 순간
    # 값을 써야 감시 태스크가 첫 heartbeat 를 쓰기 전에 멈춘 회차도 멈춤으로 보인다.
    engine = sqlite_engine(tmp_path)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE runs (run_id INTEGER PRIMARY KEY, status TEXT NOT NULL, "
                "started_at TEXT, heartbeat_at TEXT)"
            )
        )
        conn.execute(
            text("INSERT INTO runs (run_id, status) VALUES (1, 'accepted'), (2, 'queued')")
        )
    monkeypatch.setattr(repository_module, "engine", engine)

    RunRepository().mark_running(1)
    RunRepository().mark_running(2)

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT run_id, status, started_at, heartbeat_at FROM runs ORDER BY run_id")
        ).all()
    # accepted 가 아닌 회차는 그대로 둔다.
    assert [tuple(row) for row in rows] == [(1, "running", NOW, NOW), (2, "queued", None, None)]
