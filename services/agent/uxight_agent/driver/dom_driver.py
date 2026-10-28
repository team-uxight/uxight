import json
import re

from playwright.async_api import Browser, Page, Playwright, async_playwright

from ..schemas import Action
from .base import ActionResult, Driver, Observation

NAVIGATION_TIMEOUT_MS = 15_000
ACTION_TIMEOUT_MS = 5_000
ID_ATTRIBUTE = "data-ux-id"

# 관측에서 뺄 "사람 눈에 안 보이는" 글의 기준값 (관측 정제 L0.5, agent-safety §2.2 #4).
# 요소가 아니라 글(글 조각 · 버튼 value · placeholder)에만 적용한다 — 투명 select를 씌운 드롭다운
# · font-size 0 닫기 버튼 같은 정상 컨트롤은 글이 빠진 요소 줄로 남는다 (PM 결정 10/13).
# 숨기거나 투명하게 한 체크박스 · 라디오를 보이는 라벨로 바꿀지도 이 기준으로 정한다.
# 조상까지 곱한 불투명도가 이보다 낮으면 안 보인다고 본다. 0만 막으면 0.01 같은 값으로 우회된다.
MIN_OPACITY = 0.1
# 글자 크기(px)가 이보다 작으면 읽을 수 없다고 본다. 정상 페이지의 각주 · 캡션도 보통 10px 이상이다.
MIN_FONT_SIZE_PX = 6
# 요소 줄에 넣는 글 · 속성 값 하나의 최대 길이.
MAX_VALUE_LENGTH = 100

# 대상 페이지 안에서 실행되는 스크립트.
# 보이는 상호작용 요소마다 data-ux-id를 붙이고, 요소 정보를 목록으로 돌려준다.
# 사람 눈에 안 보이는 요소와 글은 뺀다 — 숨긴 곳에 심은 주입 문구가 모델 입력에 들어가지 않게.
_COLLECT_ELEMENTS_JS = """
({ idAttr, minOpacity, minFontSizePx, maxValueLength }) => {
  document.querySelectorAll(`[${idAttr}]`).forEach(el => el.removeAttribute(idAttr));

  // 사람 눈에 보이는 정도.
  // 'hidden': 요소째 안 보인다 — 크기 0 · 화면 밖 · 그려지지 않음(display:none 조상 · 닫힌 details
  //   · visibility). 이런 요소는 관측에서 뺀다.
  // 'textHidden': 요소는 있지만 글은 못 읽는다 — 투명 · 작은 글자. 요소는 남기고 글만 뺀다.
  // aria-hidden은 보이는 요소에도 붙으므로(예: 슬라이더가 보이는 슬라이드에 붙임) 보지 않는다.
  // 그 안의 주입 문구는 관측에 들어가고 mark_instructions 표시로 다룬다 (PM 결정 10/13,
  // 프롬프트에 연결하는 일은 GACA-107).
  const visibilityOf = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return 'hidden';
    if (!el.checkVisibility({ visibilityProperty: true })) return 'hidden';
    // opacity는 상속되지 않지만 조상 값과 곱해져 보이므로 조상까지 곱한다.
    // fixed 조상이 있으면 스크롤해도 화면 위치가 그대로라 문서 좌표로 바꾸지 않는다.
    let opacity = 1;
    let fixed = false;
    for (let node = el; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      opacity *= parseFloat(style.opacity);
      fixed ||= style.position === 'fixed';
    }
    // 화면 밖: 가로는 뷰포트 밖(가로 스크롤은 사람도 Agent도 거의 하지 않는다),
    // 세로는 문서 위쪽 바깥(스크롤로도 닿지 않는다). 아래쪽은 스크롤하면 보이므로 남긴다.
    if (rect.right <= 0 || rect.left >= innerWidth || rect.bottom + (fixed ? 0 : scrollY) <= 0) {
      return 'hidden';
    }
    const fontSize = parseFloat(getComputedStyle(el).fontSize);
    return opacity < minOpacity || fontSize < minFontSizePx ? 'textHidden' : 'visible';
  };

  // 글 조각을 감싼 가장 가까운 블록 요소. 블록이 바뀌는 곳만 innerText처럼 띄어 붙인다.
  const blockOf = (node) => {
    let el = node.parentElement;
    while (el && /^(inline|contents)/.test(getComputedStyle(el).display)) el = el.parentElement;
    return el;
  };

  // innerText는 투명 · 화면 밖 · 작은 글자인 자식의 글까지 담으므로
  // 글 조각마다 감싼 요소를 다시 거른다.
  const visibleText = (el) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let text = '';
    let lastBlock = null;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.nodeName === 'BR') lastBlock = null; // <br>도 innerText처럼 띄운다.
      if (node.nodeType !== Node.TEXT_NODE) continue;
      // textarea 안의 글 노드는 입력값이다 (React는 입력할 때마다 맞춰 둔다). 새지 않게 뺀다.
      if (node.parentNode.localName === 'textarea') continue; // XHTML은 nodeName이 소문자다.
      // display:contents는 상자가 없어 크기가 0이므로 상자가 있는 조상으로 판정한다.
      let parent = node.parentElement;
      while (getComputedStyle(parent).display === 'contents') parent = parent.parentElement;
      if (visibilityOf(parent) !== 'visible') continue;
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
    const visibility = visibilityOf(el);
    // 체크박스 · 라디오를 숨기거나 투명하게 하고 꾸민 라벨로 보여주는 흔한 UI — 사람은 보이는
    // 라벨을 눌러 쓴다. 이때는 라벨에 ID를 붙여 라벨을 누르게 하고, 글도 라벨 글을 쓴다.
    const toggle = tag === 'input' && ['checkbox', 'radio'].includes(el.type);
    const label = toggle && visibility !== 'visible'
      ? Array.from(el.labels).find((l) => visibleText(l).trim())
      : undefined;
    if (el.disabled || (visibility === 'hidden' && !label)) {
      continue;
    }
    (label ?? el).setAttribute(idAttr, String(nextId));
    // 입력칸의 value는 입력값(비밀번호 포함)이라 관측 어디에도 넣지 않는다 (agent-safety §1.2).
    // React처럼 입력값을 value 속성에 맞춰 두는 페이지도 있어 속성도 읽지 않는다.
    // 값이 곧 버튼 글자인 submit · button · reset(글이 보일 때만)과, 사용자가 입력할 수 없는
    // 페이지 값인 checkbox · radio만 쓴다 (라디오끼리 구별할 글이 value뿐인 경우가 많다).
    const buttonInput = tag === 'input' && ['submit', 'button', 'reset'].includes(el.type);
    const pageValue = ((buttonInput && visibility === 'visible') || toggle)
      && el.getAttribute('value');
    // select의 글은 옵션 전체라서 제외한다 (옵션은 options로 따로 제공).
    const text = (
      (label && visibleText(label))
      || (tag !== 'select' && visibleText(el))
      || el.getAttribute('aria-label')
      || pageValue
      || ''
    ).trim().replace(/\\s+/g, ' ').slice(0, maxValueLength);
    items.push({
      id: nextId,
      tag,
      type: el.getAttribute('type'),
      text,
      name: el.getAttribute('name'),
      // placeholder도 입력칸에 그려지는 글이라 글이 안 보이면 뺀다.
      placeholder: visibility === 'visible' ? el.getAttribute('placeholder') : null,
      href: el.getAttribute('href'),
      // 브라우저가 풀어 쓴 링크 목적지(<base> · 역슬래시 · 스킴 생략까지 반영). 도메인 가드가 쓴다.
      // 관측 글에는 넣지 않는다 (_format_element 는 href 속성만 쓴다).
      url: typeof el.href === 'string' ? el.href : null,
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
                        "maxValueLength": MAX_VALUE_LENGTH,
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
        # 페이지가 정한 값은 모두 _quote를 거친다 — 줄바꿈 · 따옴표로 가짜 요소 줄을 만들지 못하게.
        attrs = "".join(
            f" {key}={_quote(item[key])}"
            for key in ("type", "name", "placeholder", "href")
            if item.get(key)
        )
        # 태그 이름도 페이지가 정한다 — HTML 파서는 U+2028 · NBSP 같은 글자를 태그 이름에 넣는다.
        tag = re.sub(r"[^a-z0-9-]", "", item["tag"])
        line = f"[{item['id']}] <{tag}{attrs}> {_quote(item['text'])}"
        if item.get("options"):
            line += " options=" + ", ".join(_quote(o["value"]) for o in item["options"])
        return line


def _quote(value: str) -> str:
    """요소 줄에 넣을 값을 정리해 따옴표로 감싼다.

    글(text)과 같은 방식으로 공백 · 줄바꿈을 한 칸으로 줄이고 MAX_VALUE_LENGTH 자로 자른다.
    따옴표 · 역슬래시는 JSON 문자열처럼 이스케이프해 값이 따옴표 밖으로 나오지 못하게 한다.
    """
    return json.dumps(" ".join(value.split())[:MAX_VALUE_LENGTH], ensure_ascii=False)
