from playwright.async_api import Browser, Page, Playwright, async_playwright

from ..schemas import Action
from .base import ActionResult, Driver, Observation

NAVIGATION_TIMEOUT_MS = 15_000
ACTION_TIMEOUT_MS = 5_000
ID_ATTRIBUTE = "data-ux-id"

# 관측에서 뺄 "사람 눈에 안 보이는" 요소의 기준값 (관측 정제 L0.5, agent-safety §2.2 #4).
# 조상까지 곱한 불투명도가 이보다 낮으면 안 보인다고 본다. 0만 막으면 0.01 같은 값으로 우회된다.
MIN_OPACITY = 0.1
# 글자 크기(px)가 이보다 작으면 읽을 수 없다고 본다. 정상 페이지의 각주 · 캡션도 보통 10px 이상이다.
MIN_FONT_SIZE_PX = 6

# 대상 페이지 안에서 실행되는 스크립트.
# 보이는 상호작용 요소마다 data-ux-id를 붙이고, 요소 정보를 목록으로 돌려준다.
# 사람 눈에 안 보이는 요소와 글은 뺀다 — 숨긴 곳에 심은 주입 문구가 모델 입력에 들어가지 않게.
_COLLECT_ELEMENTS_JS = """
({ idAttr, minOpacity, minFontSizePx }) => {
  document.querySelectorAll(`[${idAttr}]`).forEach(el => el.removeAttribute(idAttr));

  // 사람 눈에 안 보이는 요소: 크기 0 · 그려지지 않음(display:none 조상 · 닫힌 details · visibility)
  // · 작은 글자 · aria-hidden · 투명 · 화면 밖.
  const isHidden = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return true;
    if (!el.checkVisibility({ visibilityProperty: true })) return true;
    const fontSize = parseFloat(getComputedStyle(el).fontSize);
    if (fontSize < minFontSizePx || el.closest('[aria-hidden="true"]')) return true;
    // opacity는 상속되지 않지만 조상 값과 곱해져 보이므로 조상까지 곱한다.
    // fixed 조상이 있으면 스크롤해도 화면 위치가 그대로라 문서 좌표로 바꾸지 않는다.
    let opacity = 1;
    let fixed = false;
    for (let node = el; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      opacity *= parseFloat(style.opacity);
      fixed ||= style.position === 'fixed';
    }
    if (opacity < minOpacity) return true;
    // 화면 밖: 가로는 뷰포트 밖(가로 스크롤은 사람도 Agent도 거의 하지 않는다),
    // 세로는 문서 위쪽 바깥(스크롤로도 닿지 않는다). 아래쪽은 스크롤하면 보이므로 남긴다.
    return rect.right <= 0 || rect.left >= innerWidth || rect.bottom + (fixed ? 0 : scrollY) <= 0;
  };

  // 글 조각을 감싼 가장 가까운 블록 요소. 블록이 바뀌는 곳만 innerText처럼 띄어 붙인다.
  const blockOf = (node) => {
    let el = node.parentElement;
    while (el && /^(inline|contents)/.test(getComputedStyle(el).display)) el = el.parentElement;
    return el;
  };

  // innerText는 투명 · 화면 밖 · 작은 글자 · aria-hidden인 자식의 글까지 담으므로
  // 글 조각마다 감싼 요소를 다시 거른다.
  const visibleText = (el) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let text = '';
    let lastBlock = null;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.nodeName === 'BR') lastBlock = null; // <br>도 innerText처럼 띄운다.
      if (node.nodeType !== Node.TEXT_NODE) continue;
      // display:contents는 상자가 없어 크기가 0이므로 상자가 있는 조상으로 판정한다.
      let parent = node.parentElement;
      while (getComputedStyle(parent).display === 'contents') parent = parent.parentElement;
      if (isHidden(parent)) continue;
      const block = blockOf(node);
      text += (block === lastBlock ? '' : ' ') + node.textContent;
      lastBlock = block;
    }
    return text;
  };

  const selector = 'a[href], button, input:not([type=hidden]), select, textarea, '
    + '[role=button], [role=link]';
  const items = [];
  let nextId = 1;
  for (const el of document.querySelectorAll(selector)) {
    const tag = el.tagName.toLowerCase();
    const hidden = isHidden(el);
    // 체크박스 · 라디오를 숨기고 꾸민 라벨로 보여주는 흔한 UI — 사람은 보이는 라벨을 눌러 쓴다.
    // 이때는 라벨에 ID를 붙여 라벨을 누르게 하고, 글도 숨은 요소의 속성 대신 라벨 글을 쓴다.
    const label = hidden && tag === 'input' && ['checkbox', 'radio'].includes(el.type)
      ? Array.from(el.labels).find((l) => visibleText(l).trim())
      : undefined;
    if (el.disabled || (hidden && !label)) {
      continue;
    }
    (label ?? el).setAttribute(idAttr, String(nextId));
    // select의 글은 옵션 전체라서 제외한다 (옵션은 options로 따로 제공).
    // textarea의 글은 입력 기본값이라 제외한다 (예전 innerText도 비어 있었다).
    const text = (
      (label && visibleText(label))
      || (tag !== 'select' && tag !== 'textarea' && visibleText(el))
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
                return await page.evaluate(
                    _COLLECT_ELEMENTS_JS,
                    {
                        "idAttr": ID_ATTRIBUTE,
                        "minOpacity": MIN_OPACITY,
                        "minFontSizePx": MIN_FONT_SIZE_PX,
                    },
                )
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
