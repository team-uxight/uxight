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

_CLEAR_MARKS_JS = """
(markAttr) => document.querySelectorAll(`[${markAttr}]`).forEach(el => el.remove())
"""


class SomDriver(DomDriver):
    """SoM(Set-of-Mark) 방식 Driver. DomDriver와 같은 번호를 화면에 박스로 그려 스크린샷을 찍는다.

    번호 · element_map · act()는 DomDriver 그대로라, 모델이 스크린샷에서 고른 번호로 바로 행동한다.
    입력칸 값은 불투명 막으로 가린 채 찍는다 (agent-safety §1.2 — 모델에 보내기 전에 가림).
    """

    async def observe(self) -> Observation:
        observation = await super().observe()
        page = self._require_page()
        await page.evaluate(
            _DRAW_MARKS_JS,
            {"idAttr": ID_ATTRIBUTE, "markAttr": MARK_ATTRIBUTE, "maskSelector": MASK_SELECTOR},
        )
        try:
            # Playwright 기본값(caret="hide")은 입력칸에 빈 style 속성을 남겨 DOM 을 바꾼다.
            # 커서는 입력칸 불투명 막에 같이 가려지므로 그대로 둔다.
            screenshot = await page.screenshot(caret="initial")
        finally:
            # 찍는 사이 페이지가 바뀌면 덧그림도 옛 문서와 함께 사라지므로 지우기 실패는 무시한다.
            # 같은 문서에 남았더라도 다음 observe()가 그리기 전에 지운다.
            with contextlib.suppress(PlaywrightError):
                await page.evaluate(_CLEAR_MARKS_JS, MARK_ATTRIBUTE)
        return dataclasses.replace(observation, screenshot=screenshot)
