"""GACA-168: 실제 페이지에서 DOM 패치 가능성을 읽기 전용으로 검증한다."""

from typing import Any

from playwright.async_api import Page
from pydantic import TypeAdapter

from ..patch.schema import Patch

_PATCH_ADAPTER = TypeAdapter(Patch)


async def validate_patch_target(
    page: Page,
    patch_kind: str,
    patch: dict[str, Any],
) -> None:
    """실제 DOM을 변경하지 않고 패치 대상의 유효성을 검사한다.

    실패 시 ValueError를 발생시킨다.
    """
    if "kind" in patch or "description" in patch:
        raise ValueError("patch must not contain kind or description")

    validated = _PATCH_ADAPTER.validate_python(
        {**patch, "kind": patch_kind}
    )

    target = page.locator(validated.target)

    try:
        target_count = await target.count()
    except Exception as exc:
        raise ValueError("Invalid target CSS selector") from exc

    if target_count != 1:
        raise ValueError(
            f"Target selector must match exactly one element: "
            f"{validated.target} (matched {target_count})"
        )

    has_text = await target.evaluate(
        """element => Boolean(
            (element.innerText || "").trim() ||
            (element.getAttribute("aria-label") || "").trim() ||
            (element.value || "").trim() ||
            (element.textContent || "").trim()
        )"""
    )

    if not has_text:
        raise ValueError("Target element has no readable text")

    if patch_kind == "relabel":
        tag_name = await target.evaluate(
            "element => element.tagName.toLowerCase()"
        )
        if tag_name in ("input", "textarea", "select"):
            raise ValueError("Relabel does not support form controls")

    if patch_kind == "move":
        destination = page.locator(validated.destination)

        try:
            destination_count = await destination.count()
        except Exception as exc:
            raise ValueError("Invalid destination CSS selector") from exc

        if destination_count != 1:
            raise ValueError(
                f"Destination selector must match exactly one element: "
                f"{validated.destination} (matched {destination_count})"
            )

        invalid_move = await target.evaluate(
            """(element, destinationSelector) => {
                const destination = document.querySelector(destinationSelector);
                return element === destination || element.contains(destination);
            }""",
            validated.destination,
        )

        if invalid_move:
            raise ValueError(
                "Cannot move an element into itself or its descendants"
            )
