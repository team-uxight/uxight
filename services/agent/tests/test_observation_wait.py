"""관측 전 기다림 (GACA-157). 늦게 뜨는 글이 첫 관측에서 빠지지 않게 한다.

LLM 없이 tests/fixtures 페이지를 Playwright 로 띄워 DomDriver · SomDriver 관측을 본다.
- late_fetch.html: 글 · 링크를 fetch 로 받아 넣는다. 응답은 ?wait= 밀리초 뒤에 온다.
- late_fade.html: 결함 사본의 미끼(DST-ANIM)처럼 글 블록이 0.5초 동안 나타난다.
"""

import asyncio
import time
from pathlib import Path

from uxight_agent.driver.base import Observation
from uxight_agent.driver.dom_driver import STILL_WAIT_MS, DomDriver
from uxight_agent.driver.som_driver import SomDriver
from uxight_agent.schemas import Action

FIXTURES = Path(__file__).parent / "fixtures"
LATE_TEXT = "11월 10일부터 11월 21일까지"


def observe_timed(url: str, driver_class: type[DomDriver] = DomDriver) -> tuple[Observation, float]:
    """url 을 띄운 직후 관측한다. 관측에 걸린 시간(초)도 돌려준다."""

    async def run() -> tuple[Observation, float]:
        async with driver_class() as driver:
            await driver.start(url)
            started = time.monotonic()
            observation = await driver.observe()
            return observation, time.monotonic() - started

    return asyncio.run(run())


def test_text_from_late_fetch_enters_first_observation(fixture_server) -> None:
    observation, _ = observe_timed(f"{fixture_server}/late_fetch.html?wait=800")

    assert LATE_TEXT in observation.text
    assert "신청하기" in [item["text"] for item in observation.element_map.values()]


def test_som_waits_for_late_fetch_too(fixture_server) -> None:
    observation, _ = observe_timed(f"{fixture_server}/late_fetch.html?wait=800", SomDriver)

    assert LATE_TEXT in observation.text
    assert observation.screenshot is not None


def test_wait_is_capped_when_request_never_ends(fixture_server) -> None:
    observation, elapsed = observe_timed(f"{fixture_server}/late_fetch.html?wait=5000")

    # 상한까지만 기다리고 관측한다. 늦게 온 글은 다음 관측에 들어온다.
    assert elapsed < STILL_WAIT_MS / 1000 + 1
    assert LATE_TEXT not in observation.text


def test_requests_of_left_page_not_waited(fixture_server) -> None:
    # 떠난 페이지의 요청은 끝 소식이 오지 않을 수 있다(route 에서 이어지기 전에 이동으로 취소됨).
    # 끝나지 않는 요청을 남겨 두고 다른 페이지로 가도, 새 페이지 관측은 그 요청을 기다리지 않는다.
    async def run() -> float:
        async with DomDriver() as driver:
            await driver.start(f"{fixture_server}/late_fetch.html?wait=800")
            first = await driver.observe()
            driver._pending_requests.add(object())  # 끝 소식이 오지 않는 요청
            link = next(i for i, item in first.element_map.items() if item["text"] == "등록 안내")
            result = await driver.act(Action(kind="click", element_id=link))
            assert result.ok, result.error
            started = time.monotonic()
            observation = await driver.observe()
            assert LATE_TEXT in observation.text  # late_fade.html 의 나타나는 글
            return time.monotonic() - started

    assert asyncio.run(run()) < STILL_WAIT_MS / 1000


def test_fading_in_text_enters_first_observation() -> None:
    # 번호를 붙일 요소가 없는 글 블록의 애니메이션도 기다린다.
    observation, _ = observe_timed((FIXTURES / "late_fade.html").as_uri())

    assert LATE_TEXT in observation.text
    assert "분할 납부는 학과 사무실에 신청한다." in observation.text


def test_decorative_animation_not_waited_in_dom_mode() -> None:
    # 학교 사본 홈의 슬라이드 진행 막대(7초)는 글도 번호 요소도 품지 않아 기다리지 않는다.
    observation, elapsed = observe_timed((FIXTURES / "som_progress.html").as_uri())

    assert observation.element_map
    assert elapsed < STILL_WAIT_MS / 1000
