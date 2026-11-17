"""GACA-170: 승인된 DOM 패치를 지정된 페이지에 순서대로 적용한다."""

from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Page

from .patcher import apply_patch


def _page_key(url: str) -> tuple[str, str, str]:
    """쿼리와 fragment를 제외한 페이지 식별자."""
    parsed = urlsplit(url)
    return (
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path or "/",
    )


async def apply_approved_patches(
    page: Page,
    patches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """현재 페이지에 해당하는 승인 패치를 목록 순서대로 적용한다."""
    results: list[dict[str, Any]] = []

    for item in patches:
        patch = item["patch"]
        page_url = patch.get("page_url")

        if not isinstance(page_url, str) or not page_url:
            results.append(
                {
                    "improvement_id": item["improvement_id"],
                    "applied": False,
                    "fail_reason": "Missing patch page_url",
                }
            )
            continue

        if _page_key(page_url) != _page_key(page.url):
            continue

        try:
            parameters = {key: value for key, value in patch.items() if key != "page_url"}

            await apply_patch(
                page,
                item["patch_kind"],
                parameters,
            )

            results.append(
                {
                    "improvement_id": item["improvement_id"],
                    "applied": True,
                    "fail_reason": None,
                }
            )

        except Exception as exc:
            results.append(
                {
                    "improvement_id": item["improvement_id"],
                    "applied": False,
                    "fail_reason": f"{type(exc).__name__}: {exc}",
                }
            )

    return results
