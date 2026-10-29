"""토큰 누적 · 하루 예산 SQL (GACA-155). CI 에는 MySQL 이 없어 SQLite 에 실제 SQL 을 돌린다."""

from pathlib import Path

import pytest
from sqlalchemy import event, text

from uxight_agent.db import create_db_engine
from uxight_agent.repositories import run_persona_repository as persona_module
from uxight_agent.repositories import run_repository as run_module
from uxight_agent.repositories.run_persona_repository import RunPersonaRepository
from uxight_agent.repositories.run_repository import RunRepository


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'agent.db'}")

    @event.listens_for(engine, "connect")
    def add_curdate(dbapi_conn, conn_rec) -> None:
        dbapi_conn.create_function("CURDATE", 0, lambda: "2026-10-28")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE policies (policy_id INT, daily_token_budget BIGINT)"))
        conn.execute(text("CREATE TABLE runs (run_id INT, tokens BIGINT, started_at TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE run_personas (run_id INT, persona_id INT, steps INT, "
                "tokens BIGINT, status TEXT)"
            )
        )
        conn.execute(text("INSERT INTO policies VALUES (1, 1000)"))
        conn.execute(
            text(
                "INSERT INTO runs VALUES (1, 300, '2026-10-27 23:00:00'), "
                "(2, NULL, '2026-10-28 09:00:00')"
            )
        )
        conn.execute(text("INSERT INTO run_personas VALUES (2, 5, 0, NULL, 'running')"))
    monkeypatch.setattr(run_module, "engine", engine)
    monkeypatch.setattr(persona_module, "engine", engine)
    return engine


def test_step_tokens_add_to_persona_and_run(engine) -> None:
    personas = RunPersonaRepository()

    personas.increment_steps(2, 5, 120)
    personas.increment_steps(2, 5, 30)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT steps, tokens FROM run_personas")).one() == (2, 150)
        assert conn.execute(text("SELECT tokens FROM runs WHERE run_id = 2")).scalar() == 150


def test_daily_left_counts_only_todays_runs(engine) -> None:
    runs = RunRepository()
    assert runs.daily_tokens_left() == 1000  # 어제 회차의 300 은 세지 않는다

    RunPersonaRepository().increment_steps(2, 5, 1000)
    assert runs.daily_tokens_left() == 0

    with engine.begin() as conn:
        conn.execute(text("UPDATE policies SET daily_token_budget = NULL"))
    assert runs.daily_tokens_left() is None
