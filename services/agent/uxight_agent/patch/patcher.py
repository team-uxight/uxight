"""GACA-167: 검증된 패치를 현재 페이지의 DOM에 적용한다."""

from typing import Any

from playwright.async_api import Page
from pydantic import TypeAdapter

from .schema import Patch

_PATCH_ADAPTER = TypeAdapter(Patch)

_APPLY_JS = """
({patch}) => {
  const findOne = (selector) => {
    const matches = document.querySelectorAll(selector);
    if (matches.length !== 1) {
      throw new Error(`Expected exactly one element for ${selector}, found ${matches.length}`);
    }
    return matches[0];
  };

  const target = findOne(patch.target);
  const visibleText = (element) =>
    (element.innerText || element.getAttribute('aria-label')
      || element.value || element.textContent || '').trim();

  const oldText = visibleText(target);
  if (!oldText) {
    throw new Error('Target has no readable text');
  }

  let description;

  switch (patch.kind) {
    case 'relabel': {
      if (target instanceof HTMLInputElement) {
        throw new Error('Relabel does not support input elements');
      }
      const textNodes = Array.from(target.childNodes).filter(
        node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
      );
      if (textNodes.length !== 1) {
        throw new Error('Relabel requires exactly one direct text node');
      }
      textNodes[0].textContent = patch.new_text;
      description = `라벨 '${oldText}' → '${patch.new_text}'`;
      break;
    }
    case 'move': {
      const destination = findOne(patch.destination);
      const destinationText = visibleText(destination);
      if (target === destination || target.contains(destination)) {
        throw new Error('Cannot move an element into itself or its descendants');
      }
      switch (patch.position) {
        case 'before':
          destination.before(target);
          break;
        case 'after':
          destination.after(target);
          break;
        case 'first':
          destination.prepend(target);
          break;
        case 'last':
          destination.append(target);
          break;
      }
      description = `'${oldText}' 요소를 '${destinationText}' 기준 `
        + `${patch.position} 위치로 이동`;
      break;
    }
    case 'highlight': {
      if (patch.style === 'outline') {
        target.style.outline = '3px solid #2563eb';
        target.style.outlineOffset = '2px';
      } else {
        target.style.backgroundColor = '#fff3a3';
      }
      const shortText = oldText.replace(/\\s+/g, ' ').slice(0, 30);
      description = `'${shortText}' 요소 강조 (${patch.style})`;
      break;
    }
    case 'help_text': {
      const help = document.createElement('span');
      help.textContent = patch.text;
      help.setAttribute('data-uxight-help', 'true');
      help.style.display = 'block';
      help.style.fontSize = '0.875rem';
      help.style.marginTop = '4px';
      target.after(help);
      description = `'${oldText}' 아래 도움말 추가: '${patch.text}'`;
      break;
    }
    default:
      throw new Error('Unsupported patch kind');
  }

  return description;
}
"""


async def apply_patch(page: Page, patch_kind: str, patch: dict[str, Any]) -> dict[str, Any]:
    """패치 종류와 파라미터를 검증하고 DOM에 적용한다.

    성공하면 실제 화면의 글자를 반영한 description이 포함된 JSON을 반환한다.
    """
    if "kind" in patch:
        raise ValueError("patch must not contain kind; use patch_kind")

    payload = {**patch, "kind": patch_kind}
    validated = _PATCH_ADAPTER.validate_python(payload)
    parameters = validated.model_dump(exclude={"description"})
    description = await page.evaluate(_APPLY_JS, {"patch": parameters})
    return {**validated.model_dump(exclude={"kind"}), "description": description}
