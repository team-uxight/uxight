"""GACA-169: DOM 패치 시험 주입 및 결과 검증."""

from typing import Any

from playwright.async_api import Page

from ..patch.patcher import apply_patch


async def _snapshot(page: Page, patch: dict[str, Any]) -> dict[str, Any]:
    """패치 대상의 텍스트, 위치, 스타일, 주변 요소 상태를 수집한다."""
    return await page.evaluate(
        """({patch}) => {
            const matches = document.querySelectorAll(patch.target);
            if (matches.length !== 1) {
                throw new Error(`Expected one target, found ${matches.length}`);
            }

            const target = matches[0];
            const style = getComputedStyle(target);
            const rect = target.getBoundingClientRect();

            const visible = (element) => {
                const s = getComputedStyle(element);
                const r = element.getBoundingClientRect();
                return element.isConnected &&
                    r.width > 0 && r.height > 0 &&
                    s.display !== 'none' &&
                    s.visibility !== 'hidden' &&
                    Number(s.opacity) > 0;
            };

            const help = target.nextElementSibling;
            return {
                text: target.innerText || target.textContent || '',
                parent: target.parentElement?.outerHTML || '',
                previous: target.previousElementSibling?.outerHTML || '',
                next: target.nextElementSibling?.outerHTML || '',
                outline: style.outline,
                background: style.backgroundColor,
                visible: visible(target),
                helpText: help?.getAttribute('data-uxight-help') === 'true'
                    ? help.textContent : null,
                helpVisible: help?.getAttribute('data-uxight-help') === 'true'
                    ? visible(help) : false,
            };
        }""",
        {"patch": patch},
    )


async def validate_patch_application(
    page: Page,
    patch_kind: str,
    patch: dict[str, Any],
) -> tuple[bool, str | None]:
    """격리된 페이지에 패치를 시험 주입하고 실제 변경 여부를 검증한다."""
    try:
        before = await _snapshot(page, patch)

        if not before["visible"]:
            return False, "Patch target is not visible before application"

        await apply_patch(page, patch_kind, patch)
        after = await _snapshot(page, patch)

        if not after["visible"]:
            return False, "Patch target is not visible after application"

        if patch_kind == "relabel":
            changed = (
                before["text"].strip() != after["text"].strip()
                and after["text"].strip() == patch["new_text"].strip()
            )
        elif patch_kind == "move":
            changed = (
                before["parent"] != after["parent"]
                or before["previous"] != after["previous"]
                or before["next"] != after["next"]
            )
        elif patch_kind == "highlight":
            changed = (
                before["outline"] != after["outline"] or before["background"] != after["background"]
            )
        elif patch_kind == "help_text":
            changed = (
                after["helpText"] == patch["text"]
                and after["helpVisible"]
                and (before["helpText"] != after["helpText"] or not before["helpVisible"])
            )
        else:
            return False, f"Unsupported patch kind: {patch_kind}"

        if not changed:
            return False, "Patch produced no observable change"

        return True, None

    except Exception as exc:
        return False, f"Patch application failed: {exc}"
