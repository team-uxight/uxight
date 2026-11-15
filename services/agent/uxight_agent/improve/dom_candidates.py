"""실제 페이지에서 개선안 생성에 사용할 DOM 후보를 수집한다."""

from playwright.async_api import Page

_COLLECT_CANDIDATES_JS = """
({limit, allowedHosts, pathFallback}) => {
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

    // 위험한 행동의 버튼, 링크 및 그 내부 요소를 후보에서 제외한다.
    const normalize = (value) =>
      (value || '').normalize('NFKC')
        .replace(/[\\u200B-\\u200F\\uFEFF]/g, '');

    const unsafeLabel = (element) => {
      const label = normalize([
        element.innerText,
        element.getAttribute('aria-label'),
        element.getAttribute('title'),
        element.getAttribute('name'),
      ].filter(Boolean).join(' '));

      const compact = label.replace(/\\s+/g, '');
      const koreanVerbs = /삭제|탈퇴|해지|결제|송금|이체/;
      const englishVerbs = new RegExp(
        String.raw`\\b(?:delete|remove|withdraw|unsubscribe|` +
        String.raw`deactivate|checkout|payment|transfer)\\b`,
        'i'
      );
      const nouns = /구매|주문|제출|확정|\\bbuy\\b|\\bpurchase\\b|\\bsubmit\\b|\\bconfirm\\b/i;

      const button = element.matches(
        'button, [role="button"], input[type="submit"]'
      );

      if (koreanVerbs.test(compact)) return true;
      if (englishVerbs.test(label)) return true;
      if (button && nouns.test(compact) &&
          !/검색|조회|search|find/i.test(label)) return true;

      return false;
    };

    const unsafeLink = (link) => {
      const href = link.getAttribute('href');
      if (!href) return false;

      try {
        const url = new URL(href, document.baseURI);
        if (!['http:', 'https:'].includes(url.protocol)) return true;
        const hostKey = (value) => {
          if (value.protocol === 'file:') return 'file:';
          const port = value.port ||
            (value.protocol === 'http:' ? '80' : '443');
          return value.hostname.toLowerCase() + ':' + port;
        };

        const permitted = allowedHosts == null
          ? [hostKey(new URL(location.href))]
          : allowedHosts;

        if (!permitted.includes(hostKey(url))) return true;

        const path = decodeURIComponent(url.pathname + url.search)
          .normalize('NFKC');
        const unsafePath = new RegExp(
          '삭제|탈퇴|해지|결제|송금|이체|' +
          'delete|withdraw|unsubscribe|checkout|payment|transfer',
          'i'
        );
        return unsafePath.test(path);
      } catch {
        return true;
      }
    };

    const related = [
      el,
      ...el.querySelectorAll('a[href], button, [role="button"]'),
    ];

    const ancestor = el.closest('a[href], button, [role="button"]');
    if (ancestor && !related.includes(ancestor)) related.push(ancestor);

    if (related.some(node =>
      unsafeLabel(node) ||
      (node.matches('a[href]') && unsafeLink(node))
    )) continue;

    let selector = null;

    if (el.id) {
      selector = '#' + CSS.escape(el.id);
    } else if (tag === 'a' && el.getAttribute('href')) {
      const href = el.getAttribute('href');
      selector = 'a[href="' + CSS.escape(href) + '"]';
    } else {
      // id 가 있는 부모 아래면 '#부모 > 태그:nth-of-type(n)' 으로 찾는다.
      // pathFallback 이면 id 가 있는 가장 가까운 조상(없으면 body)까지 경로를 잇는다.
      const steps = [];
      let node = el;
      while (node.parentElement) {
        const parent = node.parentElement;
        const siblings = Array.from(parent.children)
          .filter(child => child.tagName === node.tagName);
        steps.unshift(
          node.tagName.toLowerCase() +
          ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')'
        );

        if (parent.id) {
          selector = '#' + CSS.escape(parent.id) + ' > ' + steps.join(' > ');
          break;
        }
        if (!pathFallback) break;
        if (parent === document.body) {
          selector = 'body > ' + steps.join(' > ');
          break;
        }
        node = parent;
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


async def collect_dom_candidates(
    page: Page,
    limit: int = 100,
    hosts: frozenset[str] | None = None,
) -> list[dict]:
    """DOM을 변경하지 않고 고유한 CSS 선택자를 가진 요소만 반환한다."""
    if not 1 <= limit <= 100:
        raise ValueError("limit은 1~100이어야 합니다")

    args = {"limit": limit, "pathFallback": False}
    if hosts is not None:
        args["allowedHosts"] = sorted(hosts)

    candidates = await page.evaluate(_COLLECT_CANDIDATES_JS, args)
    if candidates:
        return candidates

    # id · 링크 · id 가 있는 부모로 찾은 요소가 하나도 없으면 경로 선택자로 한 번 더 찾는다.
    # 학교 사본의 표만 있는 페이지(졸업 이수학점 표 등)는 id 가 있는 요소가 없어 후보가 0개였다.
    return await page.evaluate(_COLLECT_CANDIDATES_JS, {**args, "pathFallback": True})
