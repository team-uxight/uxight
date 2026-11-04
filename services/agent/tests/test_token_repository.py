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
        conn.execute(
            text(
                "CREATE TABLE runs (run_id INT, tokens BIGINT, started_at TEXT, "
                "cost_usd DECIMAL(10,4))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE run_personas (run_id INT, persona_id INT, steps INT, "
                "tokens BIGINT, status TEXT, cost_usd DECIMAL(10,4))"
            )
        )
        conn.execute(text("INSERT INTO policies VALUES (1, 1000)"))
        conn.execute(
            text(
                "INSERT INTO runs VALUES (1, 300, '2026-10-27 23:00:00', NULL), "
                "(2, NULL, '2026-10-28 09:00:00', NULL)"
            )
        )
        conn.execute(text("INSERT INTO run_personas VALUES (2, 5, 0, NULL, 'running', NULL)"))
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


def test_step_cost_adds_to_persona_and_run(engine) -> None:
    personas = RunPersonaRepository()

    personas.increment_steps(2, 5, 120, 0.0007)
    personas.increment_steps(2, 5, 30, 0.0014)

    with engine.connect() as conn:
        persona_cost = conn.execute(text("SELECT cost_usd FROM run_personas")).scalar()
        run_cost = conn.execute(text("SELECT cost_usd FROM runs WHERE run_id = 2")).scalar()
    assert persona_cost == pytest.approx(0.0021)
    assert run_cost == pytest.approx(0.0021)


def test_run_cost_is_sum_of_persona_rows(engine) -> None:
    # 회차 칸에는 Persona 행에 더한 값을 그대로 더한다 — 그래서 Persona 행들의 합과 같다.
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO run_personas VALUES (2, 6, 0, NULL, 'running', NULL)"))
    personas = RunPersonaRepository()

    personas.increment_steps(2, 5, 100, 0.0006)
    personas.increment_steps(2, 6, 100, 0.0007)
    personas.increment_steps(2, 5, 100, 0.0006)
    personas.increment_steps(2, 6, 100, 0.0006)

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT persona_id, cost_usd FROM run_personas")).all())
        run_cost = conn.execute(text("SELECT cost_usd FROM runs WHERE run_id = 2")).scalar()
    assert rows == pytest.approx({5: 0.0012, 6: 0.0013})
    assert run_cost == pytest.approx(0.0025)


def test_unpriced_step_keeps_cost_null_but_counts_tokens(engine) -> None:
    personas = RunPersonaRepository()

    personas.increment_steps(2, 5, 120)  # 단가 없는 모델 — 비용은 None

    with engine.connect() as conn:
        persona = conn.execute(text("SELECT tokens, cost_usd FROM run_personas")).one()
        run = conn.execute(text("SELECT tokens, cost_usd FROM runs WHERE run_id = 2")).one()
    assert tuple(persona) == (120, None)
    assert tuple(run) == (120, None)

    personas.increment_steps(2, 5, 30, 0.0003)  # 단가 있는 step 이 오면 그때부터 더한다
    personas.increment_steps(2, 5, 30)  # 비용 없는 step 이 껴도 쌓인 값은 그대로다

    with engine.connect() as conn:
        run_cost = conn.execute(text("SELECT cost_usd FROM runs WHERE run_id = 2")).scalar()
    assert run_cost == pytest.approx(0.0003)


def test_daily_left_counts_only_todays_runs(engine) -> None:
    runs = RunRepository()
    assert runs.daily_tokens_left() == 1000  # 어제 회차의 300 은 세지 않는다

    RunPersonaRepository().increment_steps(2, 5, 1000)
    assert runs.daily_tokens_left() == 0

    with engine.begin() as conn:
        conn.execute(text("UPDATE policies SET daily_token_budget = NULL"))
    assert runs.daily_tokens_left() is None
