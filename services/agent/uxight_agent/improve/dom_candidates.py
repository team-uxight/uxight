"""실제 페이지에서 개선안 생성에 사용할 DOM 후보를 수집한다."""

from playwright.async_api import Page

_COLLECT_CANDIDATES_JS = """
({limit}) => {
  const elements = document.querySelectorAll(
    'a, button, [role="button"], nav a, label, h1, h2, h3, p, span, li'
  );
  const results = [];
  const seen = new Set();

  for (const el of elements) {
    if (results.length >= limit) break;

    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();

    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      Number(style.opacity) === 0 ||
      rect.width === 0 ||
      rect.height === 0
    ) continue;

    const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
    if (!text || text.length > 120) continue;

    const tag = el.tagName.toLowerCase();
    let selector = null;

    if (el.id) {
      selector = '#' + CSS.escape(el.id);
    } else if (tag === 'a' && el.getAttribute('href')) {
      const href = el.getAttribute('href');
      selector = 'a[href="' + CSS.escape(href) + '"]';
    } else {
      const parent = el.parentElement;
      if (!parent) continue;

      const siblings = Array.from(parent.children)
        .filter(child => child.tagName === el.tagName);
      const index = siblings.indexOf(el) + 1;

      if (parent.id) {
        selector = '#' + CSS.escape(parent.id) +
          ' > ' + tag + ':nth-of-type(' + index + ')';
      }
    }

    if (!selector || seen.has(selector)) continue;

    try {
      if (document.querySelectorAll(selector).length !== 1) continue;
    } catch {
      continue;
    }

    seen.add(selector);
    results.push({
      selector,
      tag,
      text,
      role: el.getAttribute('role'),
    });
  }

  return results;
}
"""


async def collect_dom_candidates(page: Page, limit: int = 100) -> list[dict]:
    """DOM을 변경하지 않고 고유한 CSS 선택자를 가진 요소만 반환한다."""
    if not 1 <= limit <= 100:
        raise ValueError("limit은 1~100이어야 합니다")

    return await page.evaluate(_COLLECT_CANDIDATES_JS, {"limit": limit})
