import contextlib
import dataclasses

from playwright.async_api import Error as PlaywrightError

from .base import Observation
from .dom_driver import ID_ATTRIBUTE, DomDriver

MARK_ATTRIBUTE = "data-ux-som"

# 값을 가릴 입력칸. 버튼 · 체크 계열 input 은 보이는 값이 사용자 입력이 아니라서 뺀다.
MASK_SELECTOR = (
    "textarea, input:not([type=submit]):not([type=button]):not([type=reset])"
    ":not([type=image]):not([type=checkbox]):not([type=radio])"
)

# 스크린샷 한 장의 상한. 찍는 중 문서가 바뀌면 Playwright 기본값(30초)까지 멈춰
# Persona 시간을 먹는다.
SCREENSHOT_TIMEOUT_MS = 5_000
# 찍기 전에 화면이 멎기를 기다리는 최대 시간. 넘으면 그대로 찍고 찍은 뒤 확인에 맡긴다.
STILL_WAIT_MS = 1_500
# 찍은 그림을 믿을 수 없을 때(막이 빗나감 · 문서가 바뀜) 처음부터 다시 하는 횟수.
CAPTURE_ATTEMPTS = 3
# 기다릴 움직임의 대상. 번호를 붙이는 요소(DomDriver 가 모으는 종류)와 입력칸이다.
# 이것들을 품지 않은 장식 애니메이션은 기다리지 않는다. 학교 사본 홈의 슬라이드 진행 막대
# (7초짜리 트랜지션이 늘 돈다)까지 기다리면 관측마다 상한을 다 쓴다.
MOVING_TARGET_SELECTOR = "a[href], button, input, select, textarea, [role=button], [role=link]"

# 대상 페이지 안에서 실행되는 스크립트.
# 끝이 있는 애니메이션 · 트랜지션과 창의 부드러운 스크롤이 멎을 때까지 기다린다 (최대 maxMs).
# - 애니메이션을 끝내 버리지(finish) 않는다. 느린 애니메이션도 사람이 겪는 그대로 Agent 가 겪는다.
# - 무한 반복 애니메이션(로딩 표시 · 자동 슬라이드)은 멎지 않으므로 보지 않는다.
# - 프레임 대기에 setTimeout 을 같이 건다. requestAnimationFrame 이 멈춰도 maxMs 에 끝난다.
_WAIT_STILL_JS = """
async ({ maxMs, selector }) => {
  const frame = () => new Promise((resolve) => {
    requestAnimationFrame(resolve);
    setTimeout(resolve, 100);
  });
  const matters = (target) => target != null
    && (target.matches(selector) || target.querySelector(selector) !== null);
  const start = performance.now();
  let lastY = null;
  while (performance.now() - start < maxMs) {
    const moving = document.getAnimations().some((a) => a.playState === 'running'
      && Number.isFinite(a.effect?.getComputedTiming().endTime) && matters(a.effect.target));
    if (!moving && scrollY === lastY) return;
    lastY = scrollY;
    await frame();
  }
}
"""

# 대상 페이지 안에서 실행되는 스크립트.
# 입력칸 위에는 불투명 막을, DomDriver가 붙인 번호(data-ux-id)마다 박스 · 번호를 그린다.
# - 막은 블러가 아니라 단색이다. 블러는 큰 글자(24px 이상 · zoom)를 가리지 못한다.
# - 페이지 요소의 스타일은 건드리지 않는다. 전부 컨테이너 하나에 담아 그것만 떼면 원래대로다.
# - <style> 주입은 CSP(style-src)에 막힐 수 있어 쓰지 않는다. style 속성(CSSOM)은 안 막힌다.
# - 컨테이너를 popover로 top layer에 올려야 모달 dialog 위에도 그려진다.
_DRAW_MARKS_JS = """
({ idAttr, markAttr, maskSelector }) => {
  document.querySelectorAll(`[${markAttr}]`).forEach(el => el.remove());
  const root = document.createElement('div');
  root.setAttribute(markAttr, '');
  root.setAttribute('popover', 'manual');
  root.style.cssText = 'position:fixed;inset:0 auto auto 0;width:0;height:0;margin:0;padding:0;'
    + 'border:0;overflow:visible;background:transparent;pointer-events:none;';
  // 컨테이너는 html 아래라 html zoom 이 물린다.
  // 화면 좌표(getBoundingClientRect)를 그대로 쓰도록 되돌린다.
  root.style.zoom = String(1 / document.documentElement.currentCSSZoom);
  const cover = (el, kind, css) => {
    const rect = el.getBoundingClientRect();
    const div = document.createElement('div');
    div.setAttribute(markAttr, kind);
    div.style.cssText = `position:absolute;left:${rect.left}px;top:${rect.top}px;`
      + `width:${rect.width}px;height:${rect.height}px;box-sizing:border-box;margin:0;padding:0;`
      + css;
    root.appendChild(div);
    return div;
  };
  // 막을 박스보다 먼저 넣어야 번호가 막 위에 그려진다.
  for (const el of document.querySelectorAll(maskSelector)) {
    // 안 보이는 칸(visibility hidden · opacity 0)은 값도 안 보여 가릴 것이 없다.
    // 막을 그리면 덧그림이 top layer 라 그 자리 아래의 보이는 내용을 덮는다.
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
    cover(el, 'mask', 'background:#9e9e9e;');
  }
  for (const el of document.querySelectorAll(`[${idAttr}]`)) {
    const box = cover(el, 'box', 'border:2px solid #ff0066;');
    const label = document.createElement('span');
    label.textContent = el.getAttribute(idAttr);
    // 번호 딱지(높이 14px)는 박스 바깥 왼쪽 위 모서리 바로 위에 단다.
    // 안쪽이면 짧은 링크의 첫 글자를 덮는다. 위에 자리가 없으면(화면 맨 위) 안쪽에 단다.
    // 좌표는 박스 테두리(2px) 안쪽 기준이다.
    const place = el.getBoundingClientRect().top >= 14 ? 'left:-2px;top:-16px;' : 'left:0;top:0;';
    label.style.cssText = `position:absolute;${place}padding:0 3px;`
      + 'background:#ff0066;color:#fff;font:bold 12px/14px monospace;';
    box.appendChild(label);
  }
  document.documentElement.appendChild(root);
  root.showPopover();
}
"""

# 대상 페이지 안에서 실행되는 스크립트.
# 찍은 뒤 그림을 믿을 수 있는지 보고 덧그림을 지운다. 아래가 모두 맞아야 true 다.
# - 덧그림이 남아 있다: 그린 뒤 문서가 바뀌지 않았다.
# - 요소가 있었다면 번호 박스도 있다: 번호를 붙인 뒤 그리기 전에 문서가 바뀌지 않았다.
# - 막 수와 지금 보이는 입력칸 수가 같고, 그 칸마다 같은 자리에 막이 있다: 찍는 사이 화면이
#   움직이지 않았고, 그릴 때 투명하던 칸이 나타나지도 보이던 칸이 사라지지도 않았다.
#   움직였다가 확인 전에 사라진 칸은 막 밖에 찍혔을 수 있다 (JS 로 움직이는 패널).
#   transform 아래에서는 좌표에 1/64px 오차가 있어 1px 미만 차이는 같은 자리로 본다.
_VERIFY_AND_CLEAR_JS = """
({ markAttr, maskSelector, expectBoxes }) => {
  const masks = Array.from(document.querySelectorAll(`[${markAttr}=mask]`),
    (mask) => mask.getBoundingClientRect());
  const covered = (el) => {
    const rect = el.getBoundingClientRect();
    return masks.some((mask) => ['left', 'top', 'width', 'height']
      .every((key) => Math.abs(mask[key] - rect[key]) < 1));
  };
  const visible = Array.from(document.querySelectorAll(maskSelector))
    .filter((el) => el.checkVisibility({ visibilityProperty: true, opacityProperty: true }));
  const ok = document.querySelector(`[${markAttr}=""]`) !== null
    && (!expectBoxes || document.querySelector(`[${markAttr}=box]`) !== null)
    && visible.length === masks.length
    && visible.every(covered);
  document.querySelectorAll(`[${markAttr}]`).forEach((el) => el.remove());
  return ok;
}
"""

_CLEAR_MARKS_JS = """
(markAttr) => document.querySelectorAll(`[${markAttr}]`).forEach(el => el.remove())
"""


class SomDriver(DomDriver):
    """SoM(Set-of-Mark) 방식 Driver. DomDriver와 같은 번호를 화면에 박스로 그려 스크린샷을 찍는다.

    번호 · element_map · act()는 DomDriver 그대로라, 모델이 스크린샷에서 고른 번호로 바로 행동한다.
    입력칸 값은 불투명 막으로 가린 채 찍는다 (agent-safety §1.2 — 모델에 보내기 전에 가림).
    막이 입력칸을 가렸는지 찍은 뒤 다시 확인하고, 확인하지 못한 그림은 내보내지 않는다
    (screenshot=None, 글 관측만).
    """

    async def observe(self) -> Observation:
        page = self._require_page()
        for _ in range(CAPTURE_ATTEMPTS):
            try:
                await page.evaluate(
                    _WAIT_STILL_JS, {"maxMs": STILL_WAIT_MS, "selector": MOVING_TARGET_SELECTOR}
                )
                observation = await super().observe()
                await page.evaluate(
                    _DRAW_MARKS_JS,
                    {
                        "idAttr": ID_ATTRIBUTE,
                        "markAttr": MARK_ATTRIBUTE,
                        "maskSelector": MASK_SELECTOR,
                    },
                )
                # Playwright 기본값(caret="hide")은 입력칸에 빈 style 속성을 남겨 DOM 을 바꾼다.
                # 커서는 입력칸 불투명 막에 같이 가려지므로 그대로 둔다.
                screenshot = await page.screenshot(caret="initial", timeout=SCREENSHOT_TIMEOUT_MS)
                trusted = await page.evaluate(
                    _VERIFY_AND_CLEAR_JS,
                    {
                        "markAttr": MARK_ATTRIBUTE,
                        "maskSelector": MASK_SELECTOR,
                        "expectBoxes": bool(observation.element_map),
                    },
                )
                if trusted:
                    return dataclasses.replace(observation, screenshot=screenshot)
            except PlaywrightError:  # TimeoutError 도 여기 해당한다
                # 관측 중 문서가 바뀌었거나(실행 컨텍스트가 사라짐) 찍기가 상한을 넘었다.
                # 같은 문서에 덧그림이 남았으면 지우고 처음부터 다시 한다.
                # 문서가 바뀌었으면 덧그림도 옛 문서와 함께 사라졌으므로 지우기 실패는 무시한다.
                with contextlib.suppress(PlaywrightError):
                    await page.evaluate(_CLEAR_MARKS_JS, MARK_ATTRIBUTE)
        # 가림을 확인한 그림을 얻지 못했다.
        # 값이 찍혔을 수 있는 그림은 내보내지 않고 글 관측만 돌려준다.
        return await super().observe()
