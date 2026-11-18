"""GACA-170: 승인된 DOM 패치를 지정된 페이지에 순서대로 적용한다."""

from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Page

from .patcher import apply_patch

# 넣은 패치는 <html>에 표시를 달아 같은 문서에 다시 넣지 않는다.
# 순서 선택자 옮기기는 다시 넣으면 다른 요소를 옮긴다. 새 문서에는 표시가 없어 다시 들어간다.
_HAS_MARK_JS = "(name) => document.documentElement.hasAttribute(name)"
_SET_MARK_JS = "(name) => document.documentElement.setAttribute(name, '')"


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

        mark = f"data-uxight-patch-{item['improvement_id']}"

        try:
            if await page.evaluate(_HAS_MARK_JS, mark):
                continue

            parameters = {key: value for key, value in patch.items() if key != "page_url"}

            await apply_patch(
                page,
                item["patch_kind"],
                parameters,
            )
            await page.evaluate(_SET_MARK_JS, mark)

            results.append(
                {
                    "improvement_id": item["improvement_id"],
                    "applied": True,
                    "fail_reason": None,
                }
            )

        except Exception as exc:
            # 첫 줄만 쓴다. Playwright 문구 뒤에 붙는 호출 스택은 뺀다.
            reason = f"{type(exc).__name__}: {exc}".splitlines()[0]
            results.append(
                {
                    "improvement_id": item["improvement_id"],
                    "applied": False,
                    "fail_reason": reason,
                }
            )

    return results
