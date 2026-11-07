"""runs 상태 SQL (GACA-110 리뷰). CI 에는 MySQL 이 없다.

SQLite 파일 DB 에 실제 SQL 을 돌리고, MySQL 함수 NOW() 만 흉내 낸다.
"""

from pathlib import Path

import pytest
from sqlalchemy import Engine, event, text

from uxight_agent.db import create_db_engine
from uxight_agent.repositories import run_persona_repository as persona_module
from uxight_agent.repositories import run_repository as repository_module
from uxight_agent.repositories.run_persona_repository import RunPersonaRepository
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


def test_progress_counts_token_limit_and_stuck(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 진행률은 정상 종료한 Persona 수다. 종료 이유 token_limit(전에 max_steps 로 적던 끝) ·
    # stuck 도 센다 (GACA-218). running · fail · timeout · cancelled 는 세지 않는다.
    counted = ["done", "max_steps", "token_limit", "stuck"]
    others = ["running", "fail", "timeout", "cancelled"]
    engine = sqlite_engine(tmp_path)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE runs (run_id INTEGER PRIMARY KEY, progress INTEGER)"))
        conn.execute(text("CREATE TABLE run_personas (run_id INTEGER, status TEXT)"))
        conn.execute(text("INSERT INTO runs (run_id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO run_personas VALUES (1, :status)"),
            [{"status": status} for status in counted + others],
        )
    monkeypatch.setattr(repository_module, "engine", engine)

    RunRepository().refresh_progress(1)

    with engine.begin() as conn:
        assert conn.execute(text("SELECT progress FROM runs")).scalar() == len(counted)


def test_mark_done_aggregates_persona_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """회차 지표 집계, NULL 처리, 중복 저장 방지를 검증한다."""
    from datetime import datetime

    engine = sqlite_engine(tmp_path)

    @event.listens_for(engine, "connect")
    def add_timestampdiff(dbapi_conn, conn_rec) -> None:
        def timestampdiff(unit, start, end):
            if unit != "MICROSECOND":
                raise ValueError(f"Unexpected unit: {unit}")
            delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
            return round(delta.total_seconds() * 1_000_000)

        dbapi_conn.create_function("TIMESTAMPDIFF", 3, timestampdiff)

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE runs (run_id INTEGER PRIMARY KEY, "
                "status TEXT NOT NULL, finished_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE run_personas (run_id INTEGER, steps INTEGER, "
                "backtracks INTEGER, tokens INTEGER, cost_usd REAL, "
                "started_at TEXT, finished_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE run_metrics (run_id INTEGER UNIQUE, "
                "success_rate REAL, avg_steps REAL, avg_backtracks REAL, "
                "avg_seconds REAL, tokens INTEGER, cost_usd REAL)"
            )
        )
        conn.execute(text("INSERT INTO runs (run_id, status) VALUES (1, 'running'), (2, 'queued')"))
        conn.execute(
            text(
                "INSERT INTO run_personas VALUES "
                "(1, 10, NULL, 100, 0.25, "
                "'2026-10-21 12:00:00', '2026-10-21 12:00:10'), "
                "(1, 20, NULL, 300, 0.75, "
                "'2026-10-21 12:00:00', '2026-10-21 12:00:30')"
            )
        )

    monkeypatch.setattr(repository_module, "engine", engine)

    # SQLite는 MICROSECOND를 키워드로 인식하지 않으므로
    # 테스트 실행 시에만 문자열 인자로 전달한다.
    original_execute = engine.dialect.do_execute

    def sqlite_execute(cursor, statement, parameters, context=None):
        statement = statement.replace(
            "TIMESTAMPDIFF(MICROSECOND,",
            "TIMESTAMPDIFF('MICROSECOND',",
        )
        return original_execute(cursor, statement, parameters, context)

    monkeypatch.setattr(engine.dialect, "do_execute", sqlite_execute)

    repository = RunRepository()
    repository.mark_done(1, success_rate=50.0)
    repository.mark_done(1, success_rate=99.0)
    repository.mark_done(2, success_rate=100.0)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT run_id, success_rate, avg_steps, avg_backtracks, "
                "avg_seconds, tokens, cost_usd FROM run_metrics"
            )
        ).all()
        statuses = conn.execute(text("SELECT run_id, status FROM runs ORDER BY run_id")).all()

    assert len(rows) == 1
    row = rows[0]
    assert row[0] == 1
    assert row[1] == pytest.approx(50.0)
    assert row[2] == pytest.approx(15.0)
    assert row[3] is None
    assert row[4] == pytest.approx(20.0)
    assert row[5] == 400
    assert row[6] == pytest.approx(1.0)
    assert [tuple(r) for r in statuses] == [(1, "done"), (2, "queued")]

    # 일부 Persona의 비용이 미측정이면 부분 합계를 전체 비용으로 표시하지 않는다.
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO runs (run_id, status) VALUES (3, 'running')"))
        conn.execute(
            text(
                "INSERT INTO run_personas VALUES "
                "(3, 5, NULL, 50, 0.10, "
                "'2026-10-21 12:00:00', '2026-10-21 12:00:05'), "
                "(3, 7, NULL, 70, NULL, "
                "'2026-10-21 12:00:00', '2026-10-21 12:00:07')"
            )
        )

    repository.mark_done(3, success_rate=0.0)

    with engine.begin() as conn:
        missing_cost = conn.execute(
            text(
                "SELECT avg_steps, avg_seconds, tokens, cost_usd FROM run_metrics WHERE run_id = 3"
            )
        ).one()

    assert missing_cost[0] == pytest.approx(6.0)
    assert missing_cost[1] == pytest.approx(6.0)
    assert missing_cost[2] == 120
    assert missing_cost[3] is None

    # 0-step Persona는 토큰과 비용이 모두 NULL이어도
    # 실제 비용이 측정된 다른 Persona의 합계를 무효화하지 않는다.
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO runs (run_id, status) VALUES (4, 'running')"))
        conn.execute(
            text(
                "INSERT INTO run_personas VALUES "
                "(4, 0, NULL, NULL, NULL, "
                "'2026-10-21 12:00:00', '2026-10-21 12:00:00'), "
                "(4, 5, NULL, 100, 0.25, "
                "'2026-10-21 12:00:00', '2026-10-21 12:00:05')"
            )
        )

    repository.mark_done(4, success_rate=None)

    with engine.begin() as conn:
        zero_step = conn.execute(
            text("SELECT success_rate, tokens, cost_usd FROM run_metrics WHERE run_id = 4")
        ).one()

    assert zero_step[0] is None
    assert zero_step[1] == 100
    assert zero_step[2] == pytest.approx(0.25)


def test_mark_started_updates_only_running_persona(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """슬롯 확보 시 실행 시작 시각을 갱신하고 대기·종료 Persona는 유지한다."""
    engine = sqlite_engine(tmp_path)

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE run_personas ("
                "run_id INTEGER, persona_id INTEGER, status TEXT, started_at TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO run_personas VALUES "
                "(1, 1, 'running', '2026-10-21 11:00:00'), "
                "(1, 2, 'running', '2026-10-21 11:00:00'), "
                "(1, 3, 'done', '2026-10-21 11:00:00')"
            )
        )

    monkeypatch.setattr(persona_module, "engine", engine)
    repository = RunPersonaRepository()

    # Persona 1만 슬롯을 확보했다고 가정한다.
    repository.mark_started(1, 1)
    # 이미 종료된 Persona는 시작 시각을 덮어쓰지 않는다.
    repository.mark_started(1, 3)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT persona_id, started_at FROM run_personas "
                "WHERE run_id = 1 ORDER BY persona_id"
            )
        ).all()

    assert [tuple(row) for row in rows] == [
        (1, NOW),
        (2, "2026-10-21 11:00:00"),
        (3, "2026-10-21 11:00:00"),
    ]
