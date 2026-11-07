"""GACA-168: 개선안 저장소 단위 테스트."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from uxight_agent.repositories import improvement_repository as repository_module


def make_improvement(number):
    return {
        "option_no": number,
        "finding_ids": [10],
        "patch_kind": "relabel",
        "patch": {
            "target": f"#scholarship-{number}",
            "new_text": "장학금 신청",
        },
        "rationale": "메뉴 이름이 불명확해 탐색이 지연됐다.",
        "expected_effect": "탐색 단계가 줄어들 것으로 기대된다.",
        "fix_cost": None,
    }


def fake_engine(monkeypatch, existing=0):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = existing

    @contextmanager
    def begin():
        yield connection

    engine = MagicMock()
    engine.begin.side_effect = begin

    monkeypatch.setattr(repository_module, "engine", engine)
    return connection


def test_insert_three_improvements(monkeypatch):
    connection = fake_engine(monkeypatch)

    repository_module.ImprovementRepository().insert_all(
        100,
        [make_improvement(i) for i in range(1, 4)],
    )

    assert connection.execute.call_count == 2

    rows = connection.execute.call_args.args[1]
    assert len(rows) == 3
    assert [row["option_no"] for row in rows] == [1, 2, 3]
    assert json.loads(rows[0]["finding_ids"]) == [10]
    assert json.loads(rows[0]["patch"])["target"] == "#scholarship-1"
    assert all(row["fix_cost"] is None for row in rows)


def test_reject_existing_improvements(monkeypatch):
    connection = fake_engine(monkeypatch, existing=3)

    with pytest.raises(ValueError, match="already exist"):
        repository_module.ImprovementRepository().insert_all(100, [make_improvement(1)])

    assert connection.execute.call_count == 1


def test_reject_more_than_three(monkeypatch):
    connection = fake_engine(monkeypatch)

    with pytest.raises(ValueError, match="at most 3"):
        repository_module.ImprovementRepository().insert_all(
            100, [make_improvement(i) for i in range(1, 5)]
        )

    connection.execute.assert_not_called()


def test_reject_invalid_option_order(monkeypatch):
    connection = fake_engine(monkeypatch)

    with pytest.raises(ValueError, match="consecutive"):
        repository_module.ImprovementRepository().insert_all(
            100, [make_improvement(1), make_improvement(3)]
        )

    connection.execute.assert_not_called()


def test_empty_improvements_skip_database(monkeypatch):
    connection = fake_engine(monkeypatch)

    repository_module.ImprovementRepository().insert_all(100, [])

    connection.execute.assert_not_called()
