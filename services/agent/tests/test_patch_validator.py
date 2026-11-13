"""GACA-169: 패치 시험 주입 및 실패 필터링 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uxight_agent.improve.patch_validator import validate_patch_application


@pytest.mark.anyio
async def test_valid_patch_is_accepted():
    page = MagicMock()
    before = {
        "text": "장학",
        "parent": "<nav><a>장학</a></nav>",
        "previous": "",
        "next": "",
        "outline": "none",
        "background": "rgba(0, 0, 0, 0)",
        "visible": True,
        "helpText": None,
        "helpVisible": False,
    }
    after = {
        **before,
        "text": "장학금 신청",
    }

    page.evaluate = AsyncMock(side_effect=[before, after])

    with patch(
        "uxight_agent.improve.patch_validator.apply_patch",
        new_callable=AsyncMock,
    ) as apply:
        success, reason = await validate_patch_application(
            page,
            "relabel",
            {"target": "#scholarship", "new_text": "장학금 신청"},
        )

    assert success is True
    assert reason is None
    apply.assert_awaited_once()


@pytest.mark.anyio
async def test_broken_patch_is_rejected():
    page = MagicMock()
    page.evaluate = AsyncMock(side_effect=Exception("Patch target not found"))

    with patch(
        "uxight_agent.improve.patch_validator.apply_patch",
        new_callable=AsyncMock,
    ) as apply:
        success, reason = await validate_patch_application(
            page,
            "relabel",
            {"target": "#missing", "new_text": "장학금 신청"},
        )

    assert success is False
    assert "Patch target not found" in reason
    apply.assert_not_awaited()


@pytest.fixture
def anyio_backend():
    return "asyncio"
