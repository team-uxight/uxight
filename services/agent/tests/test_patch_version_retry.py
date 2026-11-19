"""GACA-170: 실제 SQL 저장과 동일 회차 재시도 검증."""

from copy import deepcopy

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from uxight_agent.repositories import patch_version_repository as module


@pytest.fixture
def repository(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE patch_versions (
                    patch_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    improvement_id INTEGER NOT NULL,
                    patch_kind TEXT NOT NULL,
                    patch TEXT NOT NULL,
                    applied BOOLEAN NOT NULL,
                    fail_reason TEXT
                )
                """
            )
        )

    monkeypatch.setattr(module, "engine", engine)

    yield module.PatchVersionRepository(), engine
    engine.dispose()


def sample():
    return [
        {
            "improvement_id": 10,
            "patch_kind": "relabel",
            "patch": {
                "target": "#menu",
                "new_text": "장학금 안내",
                "page_url": "https://example.com/",
            },
            "applied": True,
            "fail_reason": None,
        }
    ]


def test_first_insert_is_persisted(repository):
    repo, engine = repository

    repo.insert_all(102, sample())

    with engine.connect() as conn:
        rows = (
            conn.execute(text("SELECT * FROM patch_versions WHERE run_id = 102")).mappings().all()
        )

    assert len(rows) == 1
    assert rows[0]["improvement_id"] == 10
    assert rows[0]["applied"] == 1


def test_identical_retry_does_not_duplicate(repository):
    repo, engine = repository

    repo.insert_all(102, sample())
    repo.insert_all(102, sample())

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM patch_versions WHERE run_id = 102")
        ).scalar_one()

    assert count == 1


def test_different_retry_is_rejected(repository):
    repo, engine = repository

    repo.insert_all(102, sample())

    changed = deepcopy(sample())
    changed[0]["patch"]["new_text"] = "다른 안내"

    with pytest.raises(ValueError, match="different results"):
        repo.insert_all(102, changed)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM patch_versions WHERE run_id = 102")
        ).scalar_one()

    assert count == 1


def test_failed_result_is_persisted(repository):
    repo, engine = repository

    failed = sample()
    failed[0]["applied"] = False
    failed[0]["fail_reason"] = "Target not found"

    repo.insert_all(102, failed)
    repo.insert_all(102, failed)

    with engine.connect() as conn:
        row = (
            conn.execute(text("SELECT applied, fail_reason FROM patch_versions WHERE run_id = 102"))
            .mappings()
            .one()
        )

    assert row["applied"] == 0
    assert row["fail_reason"] == "Target not found"
