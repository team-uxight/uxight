import asyncio
import contextlib
import dataclasses
import json
import re
import unicodedata

from playwright.async_api import Browser, CDPSession, Page, Playwright, async_playwright
from playwright.async_api import Error as PlaywrightError

from ..guard.destructive import destructive_path
from ..guard.domain import host_key, is_allowed, safe_destination
from ..schemas import Action
from .base import ActionResult, Driver, Observation

NAVIGATION_TIMEOUT_MS = 15_000
ACTION_TIMEOUT_MS = 5_000
ID_ATTRIBUTE = "data-ux-id"
# 행동이 연 새 창에 이동 요청이 아직 없을 때 기다리는 상한.
# 새 창의 첫 이동 요청은 보통 click 이 돌아올 때 이미 가드에 닿아 있다(10/31 측정: 60번 모두
# 1ms 안). 빈 창을 먼저 열고 주소를 나중에 넣는 스크립트를 위해 둔다.
# 행동이 새 창을 열지 않았으면 기다리지 않는다.
NEW_WINDOW_WAIT_MS = 1_000
# 늦은 이동을 되돌리는 횟수의 상한 — Persona 하나에 (GACA-224).
# 늦은 이동은 행동이 끝난 뒤 주 창이 허용 밖으로 간 것이다.
# 예: 스크립트가 나중에 바꾼 주소가 302 로 허용 밖에 보낸다.
# 되돌린 페이지가 또 허용 밖으로 보내면 되돌릴 때마다 허용 밖 요청이 한 번씩 늘고 step 만 쓴다.
# 넘으면 관측이 오류를 내 Persona 를 끝낸다.
MAX_LATE_RETURNS = 3

# 화면 그림에서 값을 가릴 입력칸. 버튼 · 체크 계열 input 은 보이는 값이 사용자 입력이 아니라서 뺀다.
MASK_SELECTOR = (
    "textarea, input:not([type=submit]):not([type=button]):not([type=reset])"
    ":not([type=image]):not([type=checkbox]):not([type=radio])"
)
# 가림 막 색. 블러가 아니라 단색이다 — 블러는 큰 글자를 가리지 못한다 (SomDriver 와 같은 색).
MASK_COLOR = "#9e9e9e"
# 스크린샷 한 장의 상한. 찍는 중 문서가 바뀌면 Playwright 기본값(30초)까지 멈춰
# Persona 시간을 먹는다.
SCREENSHOT_TIMEOUT_MS = 5_000

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
# 본문 글(Observation.text)의 안전 상한(글자). 본문은 지금 화면 안의 글뿐이라 보통 이보다 훨씬
# 짧다 — 학교 사본 71쪽을 끝까지 한 화면씩 내려 보니(10/30) 가장 긴 화면이 957자(졸업)였다.
# 글자가 아주 작거나 빽빽한 화면에서 프롬프트가 커지지 않게 막는다.
# 한 글자는 약 0.7 토큰이다(o200k_base).
MAX_TEXT_LENGTH = 3_000

# 대상 페이지 안에서 실행되는 스크립트.
# 보이는 상호작용 요소마다 data-ux-id를 붙이고, 요소 정보 목록(items)과 본문 글(text)을 돌려준다.
# 사람 눈에 안 보이는 요소와 글은 뺀다 — 숨긴 곳에 심은 주입 문구가 모델 입력에 들어가지 않게.
_COLLECT_ELEMENTS_JS = """
({ idAttr, minOpacity, minFontSizePx, maxValueLength, maxTextLength }) => {
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
      // filter 의 opacity() 도 같은 효과라 곱한다.
      for (const [, value, percent] of style.filter.matchAll(/opacity\\(([\\d.]+)(%?)\\)/g)) {
        opacity *= value / (percent ? 100 : 1);
      }
      fixed ||= style.position === 'fixed';
    }
    // 화면 밖: 가로는 뷰포트 밖(가로 스크롤은 사람도 Agent도 거의 하지 않는다),
    // 세로는 문서 위쪽 바깥(스크롤로도 닿지 않는다). 아래쪽은 스크롤하면 보이므로 남긴다.
    // 단 고정 위치(fixed) 요소는 스크롤해도 움직이지 않아, 화면 아래에 두면 끝내 안 보인다.
    if (rect.right <= 0 || rect.left >= innerWidth || rect.bottom + (fixed ? 0 : scrollY) <= 0
      || (fixed && rect.top >= innerHeight)) {
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
      // SVG 의 <a> 는 href 가 문자열이 아니다 (SVGAnimatedString) — 문서 주소에 대해 풀어 쓴다.
      url: typeof el.href === 'string' ? el.href
        : el.href?.baseVal ? new URL(el.href.baseVal, document.baseURI).href : null,
      // 이 요소가 보내는 폼의 method · action (파괴적 행동 가드가 POST 제출 · action 경로를 본다).
      form_method: el.form
        ? (el.getAttribute('formmethod') || el.form.getAttribute('method') || 'get').toLowerCase()
        : null,
      form_action: el.form ? (el.getAttribute('formaction') || el.form.action) : null,
      role: el.getAttribute('role'),
      // 글 대신 붙인 이름(aria-label · title · 안의 img alt). 관측 글에는 넣지 않고 가드만 본다.
      hint: [el.getAttribute('aria-label'), el.getAttribute('title'),
        ...Array.from(el.querySelectorAll('img[alt]'), (img) => img.alt)]
        .filter(Boolean).join(' ').slice(0, maxValueLength),
      options: tag === 'select'
        ? Array.from(el.options).map(o => ({ value: o.value, text: o.text.trim() }))
        : null,
    });
    nextId++;
  }

  // 본문 글 (GACA-217): 요소 줄에 없고 지금 화면 안에 보이는 글. 정보를 찾는 Task 는 표 · 문단을
  // 읽어야 한다. 화면 아래 글은 사람처럼 스크롤해야 보인다 (PM 결정 10/30).
  // - 번호를 붙인 요소 안의 글은 요소 줄에 이미 있어 뺀다. 페이지마다 되풀이되는 메뉴 · 바닥 링크가
  //   거의 다 링크라 이것으로 빠진다. textarea 글은 입력값이라 뺀다.
  // - 보이는지는 요소 글보다 엄격하게 본다. 아래를 모두 지켜야 한다.
  //   1) 감싼 요소가 보인다(visibilityOf).
  //   2) 글 조각의 사각형(Range)이 화면 안이고, overflow hidden · clip 조상의 상자와 겹친다.
  //   3) 글자색이 투명하지 않다.
  //   그래서 text-indent 로 밀어낸 글 · 접힌 상자 · 캐러셀의 다른 슬라이드 · canvas 대체 글이
  //   빠진다. 요소 줄은 이 기준을 쓰지 않는다 — text-indent 로 숨긴 아이콘 버튼 이름
  //   ('검색창 열기')은 사람이 아이콘을 보고 아는 뜻이다.
  // - 블록이 바뀌면 줄을 바꾸고, 표는 한 행의 칸을 ' | ' 로 이어 한 줄에 둔다.
  // - 글이 있는 칸 · 블록 뒤에는 그 안 번호 요소의 번호를 ' [n]' 으로 붙인다 (GACA-222).
  //   글만 보이면 모델은 그 칸의 링크를 누를 번호를 모른다.
  //   요소 줄과 같은 번호만 쓰므로, 화면 밖 · 숨김처럼 번호가 없는 요소는 붙지 않는다.
  // - 공백을 뺀 글자 수가 maxTextLength 를 넘으면 그만 모은다. 넘게 모아야 Python 이 잘린 것을 알고
  //   … 을 붙인다. 공백 정리와 자르기는 Python 이 한다 (_body_text).
  const alphaOf = (color) => { // 계산된 색('rgba(0, 0, 0, 0.5)' · 'oklch(0 0 0 / 50%)')의 투명도
    const inner = color.slice(color.indexOf('(') + 1, color.lastIndexOf(')'));
    const alpha = inner.includes('/') ? inner.split('/')[1] : inner.split(',')[3];
    return alpha === undefined ? 1 : parseFloat(alpha) / (alpha.trim().endsWith('%') ? 100 : 1);
  };
  // clip-path: inset(위 오른쪽 아래 왼쪽) 이 남기는 상자. 값은 px 또는 %, round 는 보지 않는다.
  // 읽지 못하는 값(calc 등)이면 NaN 상자가 되어 어떤 글과도 겹치지 않는다.
  const insetBox = (el, clipPath) => {
    const [top, right = top, bottom = top, left = right] = clipPath
      .slice(6, clipPath.indexOf(')')).split(' round ')[0].trim().split(/\\s+/);
    const r = el.getBoundingClientRect();
    const size = (value, length) => parseFloat(value) * (value.endsWith('%') ? length / 100 : 1);
    return {
      left: r.left + size(left, r.width), right: r.right - size(right, r.width),
      top: r.top + size(top, r.height), bottom: r.bottom - size(bottom, r.height),
    };
  };
  // 글 조각을 감싼 요소마다 한 번만 잰다 — 같은 요소 안의 글 조각마다 조상을 다시 오르지 않게.
  // - shown: 보이는가
  // - clips: 글을 자르는 overflow hidden · clip 조상의 상자와 clip-path: inset() 이 남기는 상자
  //   (GACA-225). inset(50%) 처럼 다 가리면 빈 상자다. 다른 모양(polygon 등)은 보지 않는다.
  // - block · cell: 줄 나눔용
  const boxes = new Map();
  const boxOf = (node) => {
    let box = boxes.get(node.parentElement);
    if (box) return box;
    // display:contents는 상자가 없어 크기가 0이므로 상자가 있는 조상으로 판정한다.
    let el = node.parentElement;
    while (getComputedStyle(el).display === 'contents') el = el.parentElement;
    const style = getComputedStyle(el);
    const clips = [];
    for (let up = el; up && up !== document.body; up = up.parentElement) {
      const upStyle = getComputedStyle(up);
      if (/hidden|clip/.test(`${upStyle.overflowX} ${upStyle.overflowY}`)) {
        clips.push(up.getBoundingClientRect());
      }
      if (upStyle.clipPath.startsWith('inset(')) clips.push(insetBox(up, upStyle.clipPath));
      if (upStyle.position === 'fixed') break; // 고정 위치 요소는 그 위 조상의 상자에 잘리지 않는다
    }
    const block = blockOf(node);
    box = {
      shown: visibilityOf(el) === 'visible'
        && Math.min(alphaOf(style.color), alphaOf(style.webkitTextFillColor)) >= minOpacity,
      clips,
      block,
      cell: block?.closest('td, th') ?? null,
    };
    boxes.set(node.parentElement, box);
    return box;
  };
  const inView = (r) => r.width > 0 && r.height > 0
    && r.top < innerHeight && r.bottom > 0 && r.left < innerWidth && r.right > 0;
  // 겹친 넓이가 있어야 겹친다 — 빈 상자(다 가린 clip-path)와는 겹치지 않는다.
  const overlaps = (r, clip) => Math.min(r.right, clip.right) > Math.max(r.left, clip.left)
    && Math.min(r.bottom, clip.bottom) > Math.max(r.top, clip.top);

  // 클릭이 걸린 칸 (GACA-225): 링크 · 버튼 · 입력칸이 아닌데 손가락 커서(cursor: pointer)인 요소.
  // 사이트 스크립트가 클릭을 받는다 — 학교 사본 졸업 페이지의 학번 칸은 누르면 새 창을 연다.
  // 번호는 위 요소들 다음부터 붙인다. 번호 요소가 넘치지 않게 아래를 모두 지킨 것만 넣는다.
  // - 가장 바깥 요소만: 손가락 커서는 자식에게 물려지므로 부모도 손가락 커서면 뺀다.
  // - 번호 요소 안이 아니고, 안에 번호 요소도 없다 — 그 번호를 누르면 된다.
  //   라벨은 이어진 입력칸에 번호가 있으면 뺀다.
  // - 칸이 보이고 보이는 글이 있다. 글은 본문 글과 같은 기준(감싼 요소 · 글자색 · 자르는 조상
  //   상자)을 지킨 글 조각만 쓰고, 가로로 화면 밖인 글(text-indent)도 뺀다. 화면 아래 글은
  //   링크처럼 남긴다 — 스크롤하면 보인다.
  //   글 없이 aria-label · title 만 있는 칸(아이콘만 있는 칸)은 번호가 없다.
  // - 글이 maxValueLength 자 안이다. 번호 요소 안 글은 본문 글에서 빠지므로, 글이 요소 줄
  //   하나에 다 들어가는 것만 넣는다. 큰 상자를 넣으면 그 안 글을 잃는다.
  // 파괴적 행동 가드는 이 요소(pointer)를 버튼으로 본다.
  const shownText = (el) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    let text = '';
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent.trim() || node.parentNode.localName === 'textarea') continue;
      range.selectNodeContents(node);
      const box = boxOf(node);
      const shown = box.shown && Array.from(range.getClientRects()).some((r) => r.width > 0
        && r.height > 0 && r.right > 0 && r.left < innerWidth && r.bottom + scrollY > 0
        && box.clips.every((clip) => overlaps(r, clip)));
      if (shown) text += ` ${node.textContent}`;
    }
    return text;
  };
  for (const el of document.body?.querySelectorAll('*') ?? []) {
    if (getComputedStyle(el).cursor !== 'pointer'
      || getComputedStyle(el.parentElement).cursor === 'pointer'
      || el.closest(`${selector}, [${idAttr}]`) || el.querySelector(`[${idAttr}]`)
      || el.control?.hasAttribute(idAttr) || visibilityOf(el) !== 'visible') {
      continue;
    }
    const text = shownText(el).trim().replace(/\\s+/g, ' ');
    if (!text || text.length > maxValueLength) continue;
    el.setAttribute(idAttr, String(nextId));
    items.push({
      id: nextId,
      tag: el.tagName.toLowerCase(),
      text,
      role: el.getAttribute('role'),
      // 가드가 볼 이름: 칸과 칸 안쪽 요소의 aria-label · title, 안의 img alt. 칸 안의 ✕
      // 아이콘(title '삭제')을 눌러도 가드가 걸리게 안쪽까지 모으고, 뒤쪽 이름을 놓치지 않게
      // 자르지 않는다. 관측 글에는 넣지 않는다.
      hint: [el, ...el.querySelectorAll('[aria-label], [title]')]
        .flatMap((named) => [named.getAttribute('aria-label'), named.getAttribute('title')])
        .concat(Array.from(el.querySelectorAll('img[alt]'), (img) => img.alt))
        .filter(Boolean).join(' '),
      pointer: true,
    });
    nextId++;
  }

  // 칸 · 블록 → 그 안 번호 요소의 번호(문서 순서).
  // 표 칸 안의 요소는 그 칸에 두고, 아니면 감싼 블록에 둔다.
  const idsByUnit = new Map();
  for (const el of document.querySelectorAll(`[${idAttr}]`)) {
    const unit = el.closest('td, th') ?? blockOf(el);
    if (!unit) continue;
    if (!idsByUnit.has(unit)) idsByUnit.set(unit, []);
    idsByUnit.get(unit).push(el.getAttribute(idAttr));
  }
  // 글을 마친 칸 · 블록의 번호를 ' [n]' 꼴로 꺼내고 비운다.
  // 바깥 글이 안쪽 블록으로 갈려 같은 칸 · 블록이 다시 나와도 번호는 한 번만 붙는다.
  const takeIds = (unit) => {
    const ids = idsByUnit.get(unit) ?? [];
    idsByUnit.delete(unit);
    return ids.map((id) => ` [${id}]`).join('');
  };
  // 표 한 행에서 from 부터 to 앞까지 칸의 자리. 글이 안 잡힌 칸(링크만 든 칸 · 빈칸)도
  // ' | ' 자리를 남겨 머리 줄과 열을 맞추고, 링크가 든 칸에는 그 요소 번호를 넣어
  // 행과 요소 줄을 잇는다.
  const skippedCells = (row, from, to) => {
    let out = '';
    for (let i = from; i < to; i++) {
      const cell = row.cells[i];
      const el = cell?.hasAttribute(idAttr) ? cell : cell?.querySelector(`[${idAttr}]`);
      out += `${el ? `[${el.getAttribute(idAttr)}]` : ''} | `;
    }
    return out;
  };
  const bodyText = () => {
    if (!document.body) return '';
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
      (node) => (node.nodeType === Node.ELEMENT_NODE
        && (node.hasAttribute(idAttr) || node.localName === 'textarea')
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    );
    const range = document.createRange();
    let text = '';
    let size = 0; // 모은 글자 수 (공백 빼고)
    let lastBlock = null;
    let lastCell = null;
    let lastUnit = null; // 방금 글의 칸(표 안이면) 또는 블록 — 번호를 붙일 자리
    for (let node = walker.nextNode(); node && size <= maxTextLength; node = walker.nextNode()) {
      if (node.localName === 'br') lastBlock = null;
      if (node.nodeType !== Node.TEXT_NODE) continue;
      const piece = node.textContent.replace(/\\s+/g, ' ');
      if (!piece.trim()) {
        if (!text.endsWith(' ')) text += ' '; // 낱말 사이 공백
        continue;
      }
      range.selectNodeContents(node);
      const rects = Array.from(range.getClientRects()).filter(inView);
      if (!rects.length) continue; // 화면 밖이거나 그려지지 않은 글 (canvas 대체 글 등)
      const box = boxOf(node);
      if (!box.shown || !rects.some((r) => box.clips.every((clip) => overlaps(r, clip)))) continue;
      if (box.block !== lastBlock) {
        const unit = box.cell ?? box.block;
        if (unit !== lastUnit) text += takeIds(lastUnit);
        lastUnit = unit;
        const row = box.cell?.parentElement;
        text += box.cell && box.cell === lastCell ? ' '
          : row && row === lastCell?.parentElement
            ? ` | ${skippedCells(row, lastCell.cellIndex + 1, box.cell.cellIndex)}`
            : `\\n${row ? skippedCells(row, 0, box.cell.cellIndex) : ''}`;
      }
      text += piece;
      size += piece.replaceAll(' ', '').length;
      lastBlock = box.block;
      lastCell = box.cell;
    }
    return text + takeIds(lastUnit);
  };

  // 글을 모은 문서의 주소 · 제목도 같이 돌려준다 (GACA-224). 한 번의 실행은 한 문서라
  // 관측의 글과 주소가 같은 문서의 것이다. 도메인 가드가 이 주소로 판정한다.
  return { items, text: bodyText(), url: location.href, title: document.title };
}
"""


class DomDriver(Driver):
    """DOM 기반 Driver. 상호작용 요소에 ID를 붙여 텍스트로 보여주고, 그 ID로 행동한다."""

    def __init__(self, headless: bool = True, allowed_hosts: frozenset[str] = frozenset()) -> None:
        super().__init__(allowed_hosts)
        self._blocked_url: str | None = None  # 이번 행동 중 끊은 이동의 목적지
        # 이번 행동의 새 창 · 이동 요청 (GACA-225). act() 가 행동마다 비운다.
        # - _page_opened_window: 행동 전에 주 창이 스스로 창을 열었다 — 새 창을 따르지 않는다
        # - _navigated: 주 창이나 새 창의 이동 요청이 왔다 (새 창 기다림을 끝낸다)
        # - _main_navigated: 주 창의 이동 요청이 왔다 — 그러면 새 창은 따르지 않는다
        # - _new_window_url: 새 창의 첫 허용 주소 GET. 따를지는 act() 가 정한다
        self._page_opened_window = False
        self._navigated = asyncio.Event()
        self._main_navigated = False
        self._new_window_url: str | None = None
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._cdp: CDPSession | None = None  # 새 창을 보고 닫는 브라우저 CDP 세션
        # 닫은 창의 CDP target id. 다른 프로세스에 뜬 창(target=_blank 기본값)은 닫은 뒤에도
        # 수십 ms 동안 목록에 남는다(10/31 측정: 35ms) — 다음 행동이 남은 창으로 보지 않게.
        self._closed_windows: set[str] = set()
        self._target_id: str | None = None  # 주 창의 CDP target id (= 주 창 main frame id)
        self._context_id: str | None = None  # 주 창의 browser context id
        self._element_map: dict[int, dict] = {}
        # 늦은 이동 (GACA-224)
        # - _last_allowed_url: 마지막으로 허용 안에서 본 주 창 주소. 늦은 이동을 되돌릴 곳이다.
        #   _remember() 만 바꾼다
        # - _late_returns: 늦은 이동을 되돌린 횟수 (MAX_LATE_RETURNS 까지)
        # - _left_url: 이번 관측 전에 되돌린 허용 밖 주소 (계정 · 쿼리 뺌). observe() 가 시작할 때
        #   비운다
        self._last_allowed_url: str | None = None
        self._late_returns = 0
        self._left_url: str | None = None

    async def start(self, url: str) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._page = await self._browser.new_page()
        session = await self._page.context.new_cdp_session(self._page)
        target = (await session.send("Target.getTargetInfo"))["targetInfo"]
        self._target_id, self._context_id = target["targetId"], target["browserContextId"]
        await session.detach()
        self._cdp = await self._browser.new_browser_cdp_session()
        start_host = host_key(url)
        if start_host:
            self._allowed_hosts = self._allowed_hosts | {start_host}
        # 새 창(target=_blank)도 같은 context 라 함께 막힌다.
        await self._page.context.route("**/*", self._guard_navigation)
        await self._page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        self._remember(url)

    async def _guard_navigation(self, route) -> None:
        """허용 밖으로 가는 top-level 이동 요청을 끊는다 (guard.domain 2단계).

        이미지 · 스크립트 같은 하위 요청과 iframe 이동은 그대로 둔다 — 화면이 사람이 보는 것과
        달라지지 않게. 'aborted' 로 끊으면 오류 화면 없이 지금 페이지에 머문다.
        주 창(self._page)이 아닌 창, 곧 새 창의 이동은 주소와 상관없이 끊는다. 허용된 주소도
        리다이렉트로 허용 밖 주소에 닿을 수 있고(route 는 리다이렉트를 보지 못한다), 새 창에는
        3단계 되돌리기가 없다. Agent 는 새 창을 보지 않는다.
        대신 행동 중 새 창의 첫 허용 주소 GET 을 남긴다 (GACA-225). 행동이 연 창이면 act() 가
        그 주소를 주 창에서 연다. 주 창의 이동이라 이 처리기와 3단계 되돌리기를 거친다.
        이 처리기는 예외를 내면 안 된다. 낸 예외는 Playwright 가 다음 API 호출(관측의 page.evaluate
        등)에서 대신 던지고, 그 요청은 이어지지도 끊기지도 않은 채 멈춘다 (GACA-223).
        그래서 판정하지 못한 이동은 끊고, 끊기 · 잇기에서 난 오류는 밖으로 내지 않는다.
        """
        request = route.request
        block = outside = False
        try:
            if request.is_navigation_request():
                outside = not is_allowed(request.url, self._allowed_hosts)
                try:
                    frame = request.frame
                except PlaywrightError:
                    # 주소를 넘겨 연 새 창(target=_blank · window.open)은 첫 이동부터 끊기므로
                    # Playwright 가 끝내 그 창을 모른다. 그래서 그 창의 모든 이동에서
                    # request.frame 이 오류를 낸다.
                    frame = None
                new_window = frame is None or frame.page is not self._page
                top = frame is None or frame.parent_frame is None
                block = new_window or (outside and top)
                if top:
                    # 폼 POST 는 주 창에서 다시 보낼 수 없어(page.goto 는 GET) 남기지 않는다.
                    if not new_window:
                        self._main_navigated = True
                    elif self._new_window_url is None and not outside and request.method == "GET":
                        self._new_window_url = request.url
                    self._navigated.set()
        except Exception:
            block = True
        try:
            if block:
                if outside:
                    self._blocked_url = request.url
                await route.abort("aborted")
            else:
                await route.continue_()
        except PlaywrightError:
            # 창 · 브라우저가 닫히는 중이거나, 다른 곳에서 난 오류를 Playwright 가 여기서 대신
            # 던졌다. 끊거나 잇지 못한 요청은 멈춘 채 진행되지 않는다.
            pass

    async def observe(self) -> Observation:
        self._left_url = None
        observation = await self._observe_page()
        # step 로그용 화면 그림 (모델에는 글 관측만 간다). 입력칸은 단색 막으로 가린 채 찍는다.
        # 찍지 못하면 그림 없이 진행한다 — 그 step 로그의 screenshot 은 null 이다.
        page = self._require_page()
        try:
            screenshot = await page.screenshot(
                mask=[page.locator(MASK_SELECTOR)],
                mask_color=MASK_COLOR,
                caret="initial",
                timeout=SCREENSHOT_TIMEOUT_MS,
            )
        except PlaywrightError:
            screenshot = None
        # 찍는 사이 주 창이 허용 밖으로 갔으면 허용 밖 페이지의 그림일 수 있어 버린다 (GACA-224).
        if not is_allowed(page.url, self._allowed_hosts):
            screenshot = None
        return dataclasses.replace(observation, screenshot=screenshot)

    async def _observe_page(self) -> Observation:
        """요소 목록과 본문 글만 관측한다 (화면 그림 없음).

        주 창이 허용 밖에 와 있으면 모으기 전에 마지막 허용 주소로 되돌린다 (늦은 이동, GACA-224).
        행동이 끝난 뒤 일어난 이동은 act() 의 3단계 되돌리기를 거치지 않는다.
        허용 판정은 글을 모은 문서의 주소로 한다(_collect_elements 가 글과 함께 돌려준다).
        모으는 사이 허용 밖으로 갔으면 모은 것을 버리고 다시 되돌린다.
        허용 밖 페이지의 글 · 요소 · 제목은 관측에 넣지 않는다.
        되돌린 허용 밖 주소는 관측의 blocked 로 남는다.
        되돌리기는 상한이 있어(_return_inside) 이 반복은 끝난다. 되돌리지 못하면 오류를 낸다.
        """
        page = self._require_page()
        while True:
            url = page.url
            if is_allowed(url, self._allowed_hosts):
                collected = await self._collect_elements(page)
                url = collected["url"]
                if is_allowed(url, self._allowed_hosts):
                    break
            self._left_url = self._left_url or safe_destination(url)
            if not await self._return_inside():
                safe = safe_destination(page.url)
                raise RuntimeError(f"주 창을 허용 주소로 되돌리지 못했습니다: {safe}")
        self._remember(url)
        items = collected["items"]
        self._element_map = {item["id"]: item for item in items}
        return Observation(
            url=url,
            title=_clean(collected["title"]),
            dom="\n".join(self._format_element(item) for item in items),
            text=_body_text(collected["text"]),
            element_map=dict(self._element_map),
            blocked=self._left_url,
        )

    async def _return_inside(self) -> bool:
        """허용 밖에 와 있는 주 창을 마지막 허용 주소로 되돌린다 (GACA-224). 돌아왔으면 True.

        늦은 이동을 되돌리는 것은 Persona 하나에 MAX_LATE_RETURNS 번까지다.
        되돌린 주소도 허용 밖으로 보내면(리다이렉트) 더 되돌리지 않는다.
        다시 가 봐야 허용 밖 요청만 는다.
        되돌릴 곳이 없으면(시작 주소부터 파괴적 경로) 되돌리지 않는다.
        """
        if self._last_allowed_url is None or self._late_returns >= MAX_LATE_RETURNS:
            return False
        self._late_returns += 1
        page = self._require_page()
        with contextlib.suppress(PlaywrightError):
            await page.goto(
                self._last_allowed_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS
            )
        if is_allowed(page.url, self._allowed_hosts):
            return True
        self._late_returns = MAX_LATE_RETURNS
        return False

    def _remember(self, url: str) -> None:
        """주 창 주소를 되돌릴 곳으로 기억한다 (GACA-224).

        허용 밖 주소와 파괴적 경로(destructive_path — /member/delete.do 등)는 기억하지 않고
        이전 값을 둔다. 되돌리기는 그 주소를 다시 GET 한다 — 상태를 바꾸는 GET 을 되풀이하지
        않게.
        """
        if is_allowed(url, self._allowed_hosts) and not destructive_path(url):
            self._last_allowed_url = url

    async def act(self, action: Action) -> ActionResult:
        # 요구사항: 실패 시 예외 대신 결과를 반환한다. 어떤 예외든 여기서 결과로 바꾼다.
        page = self._require_page()
        before = page.url
        if not is_allowed(before, self._allowed_hosts):
            # 관측 뒤 주 창이 늦게 허용 밖으로 갔다 — 행동을 정하는 사이 일어난 이동 (GACA-224).
            # 허용 밖 페이지에서는 행동하지 않는다. 마지막 허용 주소로 되돌리고 차단으로 남긴다.
            await self._return_inside()
            safe = safe_destination(before)
            return ActionResult(
                ok=False,
                error=f"Action blocked by domain policy: {safe}",
                error_code="DOMAIN_BLOCKED",
                destination=safe,
                late=True,
                url_after=page.url if is_allowed(page.url, self._allowed_hosts) else None,
            )
        # 행동 전부터 열린 창(페이지가 스스로 띄운 창)은 먼저 닫는다. 그래야 행동 뒤에 보는 창과
        # 새 창의 이동 요청이 이번 행동의 것이다 (GACA-225).
        # 그중 주 창이 연 창이 있었으면 이번 행동의 새 창도 따르지 않는다. 타이머로 창을 거듭 여는
        # 페이지에서는 행동 중에 생긴 창을 클릭이 열었는지 가를 수 없다.
        leftovers = await self._windows()
        await self._close_windows(leftovers)
        self._page_opened_window = any(
            window.get("openerFrameId") == self._target_id for window in leftovers
        )
        self._blocked_url = None
        self._main_navigated = False
        self._new_window_url = None
        self._navigated.clear()
        try:
            result = await self._perform(action)
            url = await self._new_window_to_follow()
            if url and (reason := destructive_path(url)):
                # 새 창으로 열려던 주소도 링크 목적지처럼 파괴적 행동 가드의 경로 검사를 거친다.
                result = ActionResult(
                    ok=False,
                    error=f"Action blocked as destructive: {reason}",
                    error_code="DESTRUCTIVE_ACTION_BLOCKED",
                )
            elif url:
                # 새 창으로 열려던 허용 주소를 주 창에서 연다 (GACA-225).
                # 사람은 새 탭에서 이어 본다. step 로그의 url_after 가 이 주소가 된다.
                # 허용 밖으로 리다이렉트되면 아래 3단계가 되돌린다.
                await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        except Exception as e:
            first_line = str(e).splitlines()[0] if str(e) else ""
            result = ActionResult(ok=False, error=f"{type(e).__name__}: {first_line}")
        # 요청을 끊지 못한 이동(리다이렉트 등)으로 허용 밖에 와 있으면 행동 전 주소로 되돌린다
        # (guard.domain 3단계). 행동 전 주소가 파괴적 경로면 다시 GET 하지 않고
        # 마지막으로 기억한 주소로 되돌린다 (GACA-224).
        outside = None if is_allowed(page.url, self._allowed_hosts) else page.url
        back_to = self._last_allowed_url if destructive_path(before) else before
        if outside and back_to:
            try:
                await page.goto(
                    back_to, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS
                )
            except PlaywrightError:
                pass  # 되돌리지 못해도 차단으로 기록한다. 다음 관측이 마지막 허용 주소로 되돌린다.
        destination = self._blocked_url or outside
        if destination:
            safe = safe_destination(destination)
            result = ActionResult(
                ok=False,
                error=f"Action blocked by domain policy: {safe}",
                error_code="DOMAIN_BLOCKED",
                destination=safe,
                late=result.late,  # _perform 이 행동하지 않은 늦은 이동이면 그대로 둔다
            )
        self._remember(page.url)
        # 행동 뒤 주소 (step 로그 result.url_after). 되돌리지 못해 허용 밖이면 None 이다 —
        # 허용 밖 주소의 원문(계정 · 토큰이 들어 있을 수 있다)을 로그에 남기지 않는다.
        url_after = page.url if is_allowed(page.url, self._allowed_hosts) else None
        return dataclasses.replace(result, url_after=url_after)

    async def _new_window_to_follow(self) -> str | None:
        """이번 행동이 연 새 창을 닫고, 그 대신 주 창에서 열 주소를 돌려준다 (GACA-225).

        행동 전부터 있던 창은 act() 가 먼저 닫았으므로, 지금 열린 창은 이번 행동 중 생긴 창이다.
        따르는 것은 행동이 연 창뿐이다 (_opened_by_action). iframe 이 연 창 · 한꺼번에 둘 이상
        열린 창은 따르지 않는다. 이번 행동에서 이동을 끊었거나 주 창이 움직였어도 따르지 않는다.
        따를 창의 이동 요청이 아직 없으면 NEW_WINDOW_WAIT_MS 까지 기다린다.
        기다리는 사이 다른 창이 열리면 따르지 않는다 — 남은 주소가 그 창의 것일 수 있다.
        """
        windows = await self._windows()
        if self._opened_by_action(windows) and not self._navigated.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._navigated.wait(), NEW_WINDOW_WAIT_MS / 1000)
            windows = await self._windows()
        await self._close_windows(windows)
        if self._opened_by_action(windows) and not (self._blocked_url or self._main_navigated):
            return self._new_window_url
        return None

    def _opened_by_action(self, windows: list[dict]) -> bool:
        """행동이 연 창이다: 새 창이 하나뿐이고, 그 창을 주 창의 main frame 이 열었다.

        여는 frame 은 CDP openerFrameId 로 본다. page target 의 id 는 그 main frame 의 id 와 같다.
        행동 전에 주 창이 스스로 창을 연 페이지면 아니라고 본다 (act() 의 _page_opened_window).
        """
        return (
            not self._page_opened_window
            and len(windows) == 1
            and windows[0].get("openerFrameId") == self._target_id
        )

    async def _windows(self) -> list[dict]:
        """주 창 말고 열린 창 (CDP target 정보 — 주 창과 같은 browser context 의 page 만).

        가드가 이동을 끊은 새 창은 빈 창으로 브라우저가 닫힐 때까지 남는다. Playwright 가 모르는
        창도 있어 CDP 로 보고 닫는다. CDP 오류면 빈 목록이다 — 창을 닫지도 따르지도 않는다.
        """
        try:
            targets = (await self._cdp.send("Target.getTargets"))["targetInfos"]
        except PlaywrightError:
            return []
        return [
            target
            for target in targets
            if target["type"] == "page"
            and target.get("browserContextId") == self._context_id
            and target["targetId"] not in (self._target_id, *self._closed_windows)
        ]

    async def _close_windows(self, windows: list[dict]) -> None:
        """창을 닫는다. 닫지 못한 창은 넘어간다 — 다음 행동 때 다시 닫는다.

        target=_blank 링크는 창마다 renderer 프로세스를 하나씩 띄운다(10/31 측정: 20번 누르면
        renderer 22개, 메모리 약 1.4GB).
        """
        for window in windows:
            with contextlib.suppress(PlaywrightError):
                await self._cdp.send("Target.closeTarget", {"targetId": window["targetId"]})
                self._closed_windows.add(window["targetId"])

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    async def _collect_elements(self, page: Page) -> dict:
        """{"items": 요소 목록, "text": 본문 글, "url" · "title": 그 문서의 주소 · 제목}.

        한 스크립트로 모아 모두 같은 문서의 것이다.
        """
        # 직전 click으로 페이지 이동이 진행 중이면 실행 컨텍스트가 사라질 수 있어 한 번 더 시도한다.
        # 페이지 스크립트가 새 창을 여는 순간에 관측이 끼면 TreeWalker 의 거르개(JS 콜백)를 부르지
        # 못해 실패한다('callback is no longer runnable'). 이것도 한 번 더 시도한다 (GACA-225).
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
                        "maxTextLength": MAX_TEXT_LENGTH,
                    },
                )
            except Exception as e:
                transient = ("Execution context was destroyed", "callback is no longer runnable")
                if attempt == 1 or not any(message in str(e) for message in transient):
                    raise
        return {"items": [], "text": ""}

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
            return ActionResult(
                ok=False,
                error=f"element_map에 없는 요소 ID: {action.element_id}",
                error_code="ELEMENT_NOT_FOUND",
            )
        if action.kind == "type" and action.value is None:
            return ActionResult(ok=False, error="type 행동에 입력값(value)이 없습니다")
        if action.kind not in ("click", "type"):
            return ActionResult(ok=False, error=f"지원하지 않는 행동: {action.kind}")
        # 번호 요소를 handle 로 잡고, 그 요소가 든 문서가 허용 주소일 때만 그 handle 에 행동한다
        # (GACA-224). Locator 는 행동을 기다리는 사이(가림 막 · 애니메이션) 문서가 바뀌면
        # 새 문서에서 같은 번호를 다시 찾는다.
        # 허용 밖 페이지가 같은 번호 속성을 심어 두면 거기서 누르고, 입력값이 허용 밖으로 나간다.
        # handle 은 문서가 바뀌면 떨어져 행동이 실패한다.
        # 문서 주소는 handle 이 든 문서에서 location.href 로 읽는다. location 은 페이지가
        # 다시 정의할 수 없다. el.ownerDocument 같은 보통 속성은 허용 밖 페이지가 위조한다.
        locator = page.locator(f'[{ID_ATTRIBUTE}="{action.element_id}"]')
        handle = await locator.element_handle(timeout=ACTION_TIMEOUT_MS)
        document = await handle.evaluate("() => location.href")
        if not is_allowed(document, self._allowed_hosts):
            # 찾는 사이 페이지가 스스로 허용 밖으로 갔다 — 행동하지 않은 늦은 이동이다.
            safe = safe_destination(document)
            return ActionResult(
                ok=False,
                error=f"Action blocked by domain policy: {safe}",
                error_code="DOMAIN_BLOCKED",
                destination=safe,
                late=True,
            )
        if action.kind == "click":
            await handle.click(timeout=ACTION_TIMEOUT_MS)
        else:
            await handle.fill(action.value, timeout=ACTION_TIMEOUT_MS)
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
    """요소 줄에 넣을 값을 정리해(_clean) MAX_VALUE_LENGTH 자로 자르고 따옴표로 감싼다.

    따옴표 · 역슬래시는 JSON 문자열처럼 이스케이프해 값이 따옴표 밖으로 나오지 못하게 한다.
    """
    return json.dumps(_clean(value)[:MAX_VALUE_LENGTH], ensure_ascii=False)


def _body_text(raw: str) -> str:
    """본문 글을 줄마다 정리하고(_clean) 빈 줄을 뺀 뒤 MAX_TEXT_LENGTH 자로 자른다.

    줄은 페이지 스크립트가 블록마다 나눈 것이다. 자르면 끝에 … 을 붙여 뒤에 글이 더 있음을 알린다.
    """
    lines = (_clean(line) for line in raw.splitlines())
    text = "\n".join(line for line in lines if line)
    return text if len(text) <= MAX_TEXT_LENGTH else text[:MAX_TEXT_LENGTH] + "…"


def _clean(value: str) -> str:
    """페이지 글 한 줄을 프롬프트에 넣기 전에 다듬는다.

    - 안 보이는 제어 · 서식 문자(유니코드 Cc · Cf)를 지운다. \\x08 · \\x01 · U+202E 를 남기면 JSON
      이스케이프(\\b · \\u0001)가 낱말에 붙어 지시문 패턴이 빗나간다.
    - NFC 로 맞춘다. 첫가끝 자모로 풀어 쓴 글은 지시문 표시가 따옴표까지 넓어진다.
    - 공백 · 줄바꿈은 한 칸으로 줄인다.
    """
    kept = "".join(c for c in value if c.isspace() or unicodedata.category(c) not in ("Cc", "Cf"))
    return " ".join(unicodedata.normalize("NFC", kept).split())
