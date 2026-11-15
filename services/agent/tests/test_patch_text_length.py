"""GACA-169: 개선안 패치 문구 길이 제한 테스트."""

import pytest
from pydantic import TypeAdapter, ValidationError

from uxight_agent.patch.schema import Patch

adapter = TypeAdapter(Patch)


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("relabel", "new_text"),
        ("help_text", "text"),
    ],
)
def test_patch_text_length_limit(kind, field):
    base = {"target": "#menu", "kind": kind}

    valid = adapter.validate_python({**base, field: "가" * 200})
    assert getattr(valid, field) == "가" * 200

    with pytest.raises(ValidationError):
        adapter.validate_python({**base, field: "가" * 201})
