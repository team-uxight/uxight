"""findings INSERT SQL (GACA-165). CI 에는 MySQL 이 없어 SQLite 파일 DB 에 실제 SQL 을 돌린다."""

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from uxight_agent.db import create_db_engine
from uxight_agent.diagnose.findings import Finding
from uxight_agent.repositories import finding_repository as repository_module
from uxight_agent.repositories.finding_repository import FindingRepository

EVIDENCE = [{"persona_id": 3, "step_from": 4, "step_to": 7, "url": "https://school.test/학사"}]


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'agent.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE findings (finding_id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, "
                "taxonomy TEXT NOT NULL, severity TEXT NOT NULL, evidence TEXT NOT NULL, "
                "summary TEXT)"
            )
        )
    monkeypatch.setattr(repository_module, "engine", engine)
    return engine


def test_insert_all_writes_one_row_per_finding(engine) -> None:
    FindingRepository().insert_all(
        7,
        [
            Finding("task_failure", "high", EVIDENCE),
            Finding("excessive_steps", "low", [], summary="설명"),
        ],
    )

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT run_id, taxonomy, severity, evidence, summary FROM findings")
        ).all()
    assert [(r.run_id, r.taxonomy, r.severity, r.summary) for r in rows] == [
        (7, "task_failure", "high", None),
        (7, "excessive_steps", "low", "설명"),
    ]
    # evidence 는 Spring 이 읽는 snake_case JSON 배열 그대로 — 한글 URL 도 그대로 둔다.
    assert json.loads(rows[0].evidence) == EVIDENCE


def test_insert_all_with_no_findings_writes_nothing(engine) -> None:
    FindingRepository().insert_all(7, [])

    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM findings")).scalar() == 0
