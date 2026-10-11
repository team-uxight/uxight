from playwright.async_api import Browser, Page, Playwright, async_playwright

from ..schemas import Action
from .base import ActionResult, Driver, Observation

NAVIGATION_TIMEOUT_MS = 15_000
ACTION_TIMEOUT_MS = 5_000
ID_ATTRIBUTE = "data-ux-id"

# 대상 페이지 안에서 실행되는 스크립트.
# 보이는 상호작용 요소마다 data-ux-id를 붙이고, 요소 정보를 목록으로 돌려준다.
_COLLECT_ELEMENTS_JS = """
(idAttr) => {
  document.querySelectorAll(`[${idAttr}]`).forEach(el => el.removeAttribute(idAttr));
  const selector = 'a[href], button, input:not([type=hidden]), select, textarea, '
    + '[role=button], [role=link]';
  const items = [];
  let nextId = 1;
  for (const el of document.querySelectorAll(selector)) {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (rect.width === 0 || rect.height === 0 || style.visibility === 'hidden' || el.disabled) {
      continue;
    }
    el.setAttribute(idAttr, String(nextId));
    const tag = el.tagName.toLowerCase();
    // select의 innerText는 옵션 전체라서 제외한다 (옵션은 options로 따로 제공).
    const text = (
      (tag !== 'select' && el.innerText)
      || el.getAttribute('aria-label')
      || el.getAttribute('value')
      || ''
    ).trim().replace(/\\s+/g, ' ').slice(0, 100);
    items.push({
      id: nextId,
      tag,
      type: el.getAttribute('type'),
      text,
      name: el.getAttribute('name'),
      placeholder: el.getAttribute('placeholder'),
      href: el.getAttribute('href'),
      options: tag === 'select'
        ? Array.from(el.options).map(o => ({ value: o.value, text: o.text.trim() }))
        : null,
    });
    nextId++;
  }
  return items;
}
"""


class DomDriver(Driver):
    """DOM 기반 Driver. 상호작용 요소에 ID를 붙여 텍스트로 보여주고, 그 ID로 행동한다."""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._element_map: dict[int, dict] = {}

    async def start(self, url: str) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._page = await self._browser.new_page()
        await self._page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)

    async def observe(self) -> Observation:
        page = self._require_page()
        items = await self._collect_elements(page)
        self._element_map = {item["id"]: item for item in items}
        return Observation(
            url=page.url,
            title=await page.title(),
            dom="\n".join(self._format_element(item) for item in items),
            element_map=dict(self._element_map),
        )

    async def act(self, action: Action) -> ActionResult:
        # 요구사항: 실패 시 예외 대신 결과를 반환한다. 어떤 예외든 여기서 결과로 바꾼다.
        try:
            return await self._perform(action)
        except Exception as e:
            first_line = str(e).splitlines()[0] if str(e) else ""
            return ActionResult(ok=False, error=f"{type(e).__name__}: {first_line}")

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    async def _collect_elements(self, page: Page) -> list[dict]:
        # 직전 click으로 페이지 이동이 진행 중이면 실행 컨텍스트가 사라질 수 있어 한 번 더 시도한다.
        for attempt in range(2):
            await page.wait_for_load_state("domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            try:
                return await page.evaluate(_COLLECT_ELEMENTS_JS, ID_ATTRIBUTE)
            except Exception as e:
                if attempt == 1 or "Execution context was destroyed" not in str(e):
                    raise
        return []

    async def _perform(self, action: Action) -> ActionResult:
        page = self._require_page()

        if action.kind == "back":
            await page.go_back(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            # 시작 URL에서 뒤로 가면 브라우저 초기 페이지(about:blank)로 빠지므로
            # 되돌리고 실패로 처리한다.
            if page.url == "about:blank":
                await page.go_forward(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
                return ActionResult(ok=False, error="뒤로 갈 페이지가 없습니다")
            return ActionResult(ok=True)

        if action.kind == "done":
            # done은 Persona Agent의 종료 선언이라 브라우저에서 수행할 행동이 없다.
            return ActionResult(ok=True)

        if action.kind == "scroll":
            direction = -1 if action.value == "up" else 1
            await page.evaluate("(d) => window.scrollBy(0, d * window.innerHeight)", direction)
            return ActionResult(ok=True)

        if action.element_id not in self._element_map:
            return ActionResult(ok=False, error=f"element_map에 없는 요소 ID: {action.element_id}")
        locator = page.locator(f'[{ID_ATTRIBUTE}="{action.element_id}"]')

        if action.kind == "click":
            await locator.click(timeout=ACTION_TIMEOUT_MS)
        elif action.kind == "type":
            if action.value is None:
                return ActionResult(ok=False, error="type 행동에 입력값(value)이 없습니다")
            await locator.fill(action.value, timeout=ACTION_TIMEOUT_MS)
        else:
            return ActionResult(ok=False, error=f"지원하지 않는 행동: {action.kind}")
        return ActionResult(ok=True)

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("start()가 호출되지 않았습니다")
        return self._page

    @staticmethod
    def _format_element(item: dict) -> str:
        # 예: [3] <input type="text" name="q" placeholder="검색"> ""
        attrs = " ".join(
            f'{key}="{item[key]}"'
            for key in ("type", "name", "placeholder", "href")
            if item.get(key)
        )
        line = f'[{item["id"]}] <{item["tag"]}{" " + attrs if attrs else ""}> "{item["text"]}"'
        if item.get("options"):
            line += " options=" + ", ".join(o["value"] for o in item["options"])
        return line
