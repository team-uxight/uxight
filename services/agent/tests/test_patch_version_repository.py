"""GACA-170: 패치 적용 결과 DB 저장 테스트."""

import json
from unittest.mock import MagicMock

import pytest

from uxight_agent.repositories import patch_version_repository as repository_module


@pytest.fixture
def fake_connection(monkeypatch):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = 0

    transaction = MagicMock()
    transaction.__enter__.return_value = connection

    engine = MagicMock()
    engine.begin.return_value = transaction

    monkeypatch.setattr(repository_module, "engine", engine)
    return connection


def sample_result(applied=True, fail_reason=None):
    return {
        "improvement_id": 10,
        "patch_kind": "relabel",
        "patch": {
            "target": "#menu",
            "new_text": "장학금 안내",
            "page_url": "https://example.com/",
        },
        "applied": applied,
        "fail_reason": fail_reason,
    }


def test_insert_successful_patch(fake_connection):
    repository = repository_module.PatchVersionRepository()

    repository.insert_all(102, [sample_result()])

    assert fake_connection.execute.call_count == 2

    query, rows = fake_connection.execute.call_args.args

    assert "INSERT INTO patch_versions" in str(query)
    assert len(rows) == 1
    assert rows[0]["run_id"] == 102
    assert rows[0]["improvement_id"] == 10
    assert rows[0]["applied"] is True
    assert rows[0]["fail_reason"] is None

    patch = json.loads(rows[0]["patch"])
    assert patch["new_text"] == "장학금 안내"


def test_insert_failed_patch(fake_connection):
    repository = repository_module.PatchVersionRepository()

    repository.insert_all(
        102,
        [sample_result(False, "Target element not found")],
    )

    _, rows = fake_connection.execute.call_args.args

    assert rows[0]["applied"] is False
    assert rows[0]["fail_reason"] == "Target element not found"


def test_reject_duplicate_improvement_ids(fake_connection):
    repository = repository_module.PatchVersionRepository()

    with pytest.raises(ValueError, match="Duplicate improvement_id"):
        repository.insert_all(
            102,
            [sample_result(), sample_result()],
        )

    fake_connection.execute.assert_not_called()


def test_reject_failed_patch_without_reason(fake_connection):
    repository = repository_module.PatchVersionRepository()

    with pytest.raises(ValueError, match="fail_reason"):
        repository.insert_all(102, [sample_result(False)])

    fake_connection.execute.assert_not_called()


def test_reject_existing_patch_versions(fake_connection):
    fake_connection.execute.return_value.scalar_one.return_value = 1

    repository = repository_module.PatchVersionRepository()

    with pytest.raises(ValueError, match="already exist"):
        repository.insert_all(102, [sample_result()])

    assert fake_connection.execute.call_count == 2


def test_empty_results_do_not_access_db(fake_connection):
    repository = repository_module.PatchVersionRepository()

    repository.insert_all(102, [])

    fake_connection.execute.assert_not_called()
