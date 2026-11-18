"""GACA-170: 승인된 패치 누적 조회 테스트."""

import json
from unittest.mock import MagicMock

from uxight_agent.repositories import improvement_repository as repository_module


def test_get_approved_patches_returns_oldest_first(monkeypatch):
    """이전 회차에서 승인된 패치를 오래된 순서대로 반환한다."""
    rows = [
        {
            "improvement_id": 10,
            "source_run_id": 101,
            "patch_kind": "relabel",
            "patch": json.dumps({"target": "#menu", "new_text": "장학금 안내"}),
        },
        {
            "improvement_id": 15,
            "source_run_id": 102,
            "patch_kind": "highlight",
            "patch": json.dumps({"target": "#scholarship", "style": "outline"}),
        },
    ]

    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.all.return_value = rows

    context = MagicMock()
    context.__enter__.return_value = connection

    engine = MagicMock()
    engine.connect.return_value = context

    monkeypatch.setattr(repository_module, "engine", engine)

    repository = repository_module.ImprovementRepository()
    result = repository.get_approved_patches(103)

    assert [item["improvement_id"] for item in result] == [10, 15]
    assert result[0]["patch"]["new_text"] == "장학금 안내"
    assert result[1]["patch_kind"] == "highlight"

    query, parameters = connection.execute.call_args.args

    assert "WITH RECURSIVE" in str(query)
    assert "a.decision = 'approve'" in str(query)
    assert "ORDER BY rc.depth DESC" in str(query)
    assert parameters == {"run_id": 103}


def test_get_approved_patches_empty(monkeypatch):
    """최초 회차 등 승인 패치가 없으면 빈 목록을 반환한다."""
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.all.return_value = []

    context = MagicMock()
    context.__enter__.return_value = connection

    engine = MagicMock()
    engine.connect.return_value = context

    monkeypatch.setattr(repository_module, "engine", engine)

    repository = repository_module.ImprovementRepository()

    assert repository.get_approved_patches(101) == []
