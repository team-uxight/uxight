"""step 로그 기록 (GACA-154). 회차 하나를 진짜 DomDriver · 가짜 LLM 응답으로 돌려 steps.jsonl 과
step-<n>.png 가 행동 로그 명세(docs/persona_agent_log_schema.md 3절)대로 남는지 본다.
"""

import asyncio
import base64
import json
from datetime import datetime
from pathlib import Path

import pytest
from test_orchestrator import FakeAuditLogRepository, FakeRunPersonaRepository, FakeRunRepository

from uxight_agent.driver.dom_driver import MASK_COLOR, DomDriver
from uxight_agent.repositories.run_repository import RunSnapshot
from uxight_agent.schemas import Action
from uxight_agent.watcher import run_orchestrator as orchestrator_module
from uxight_agent.watcher.run_orchestrator import RunOrchestrator
from uxight_agent.watcher.step_log_writer import StepLogWriter

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RUN_ID, PERSONA_ID = 101, 2
PAGE = "domain_links.html"
SPEC_FIELDS = {
    "run_id",
    "persona_id",
    "step",
    "ts",
    "url",
    "observation",
    "reasoning",
    "action",
    "result",
    "blocked",
    "latency_ms",
    "tokens",
    "model",
    "task",
}
TYPED = "홍길동 202612345"

# domain_links.html 의 요소 번호: 1 안쪽 링크 · 2 원본 사이트 · ... · 8 검색 입력칸
REPLIES = [
    '{"reasoning": "검색창에 이름을 넣는다.", '
    f'"action": {{"kind": "type", "element_id": 8, "value": "{TYPED}"}}}}',
    '{"reasoning": "원본 사이트로 가 본다.", '
    '"action": {"kind": "click", "element_id": 2, "value": null}}',
    '{"reasoning": "다음',  # 깨진 JSON
    '{"reasoning": "안쪽 링크를 누른다.", '
    '"action": {"kind": "click", "element_id": 1, "value": null}}',
    '{"reasoning": "찾았다.", "action": {"kind": "done", "element_id": null, "value": null}}',
]


class CheckingWriter(StepLogWriter):
    """로그 줄을 쓸 때 그 step 의 화면 그림이 이미 다 써져 있는지 확인한다."""

    def append(self, run_id: int, persona_id: int, record: dict) -> None:
        screenshot = record["observation"]["screenshot"]
        assert screenshot is not None
        assert (self._root / screenshot).read_bytes().startswith(PNG_SIGNATURE)
        super().append(run_id, persona_id, record)


@pytest.fixture
def ran(
    fixture_server: str, scripted_llm, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request
):
    # indirect 로 (답, step 상한)을 주면 기본값(REPLIES · 10)을 바꾼다.
    replies, max_steps = getattr(request, "param", (REPLIES, 10))
    llm, requests = scripted_llm(*replies)
    personas = FakeRunPersonaRepository()
    personas.statuses[PERSONA_ID] = "running"
    audits = FakeAuditLogRepository()
    monkeypatch.setattr(orchestrator_module, "run_repository", FakeRunRepository())
    monkeypatch.setattr(orchestrator_module, "run_persona_repository", personas)
    monkeypatch.setattr(orchestrator_module, "audit_log_repository", audits)
    monkeypatch.setattr(orchestrator_module, "step_log_writer", CheckingWriter(str(tmp_path)))
    monkeypatch.setattr(
        orchestrator_module,
        "make_decider",
        lambda run_id: orchestrator_module.LLMDecider(llm, run_id=run_id),
    )
    monkeypatch.setattr(orchestrator_module, "persona_slots", asyncio.Semaphore(1))
    target = f"{fixture_server}/{PAGE}"
    snapshot = RunSnapshot(
        target_url=target,
        allowed_domains=[],
        task={
            "goal": "학사일정 찾기",
            "success_rule": "두 번째 쪽",
            "success_url": f"{target}?page=2",
        },
        personas=[{"persona_id": PERSONA_ID, "name": "p", "profile": {"web_skill": "low"}}],
        policy={"max_steps": max_steps},
    )

    asyncio.run(asyncio.wait_for(RunOrchestrator().run_personas(RUN_ID, snapshot), timeout=60))

    folder = tmp_path / str(RUN_ID) / str(PERSONA_ID)
    lines = (folder / "steps.jsonl").read_text(encoding="utf-8").splitlines()
    return {
        "steps": [json.loads(line) for line in lines],
        "folder": folder,
        "target": target,
        "personas": personas,
        "audits": audits,
        "requests": requests,
    }


def test_every_step_has_spec_fields_and_screenshot(ran) -> None:
    steps = ran["steps"]

    assert [s["step"] for s in steps] == [1, 2, 3, 4, 5]
    assert ran["personas"].statuses == {PERSONA_ID: "done"}
    for step in steps:
        assert set(step) == SPEC_FIELDS
        assert (step["run_id"], step["persona_id"]) == (RUN_ID, PERSONA_ID)
        assert datetime.fromisoformat(step["ts"]).tzinfo is not None
        observation = step["observation"]
        assert observation["mode"] == "dom"
        assert observation["screenshot"] == f"{RUN_ID}/{PERSONA_ID}/step-{step['step']}.png"
        assert (ran["folder"] / f"step-{step['step']}.png").read_bytes().startswith(PNG_SIGNATURE)
        assert isinstance(observation["elements_hash"], str)
        assert observation["element_count"] == 8
        assert set(step["result"]) == {"ok", "url_after", "error", "error_code"}
        assert set(step["latency_ms"]) == {"llm", "browser"}
        assert set(step["tokens"]) == {"prompt", "completion"}
    # 임시 파일이 남지 않는다.
    assert sorted(p.name for p in ran["folder"].iterdir()) == [
        "step-1.png",
        "step-2.png",
        "step-3.png",
        "step-4.png",
        "step-5.png",
        "steps.jsonl",
    ]


def test_typed_value_is_masked(ran) -> None:
    first = ran["steps"][0]

    assert first["action"] == {"kind": "type", "target": 8, "text": "***", "direction": None}
    assert first["result"]["ok"] is True
    assert first["model"] == "test-model"
    assert first["tokens"] == {"prompt": 11, "completion": 7}
    assert TYPED not in (ran["folder"] / "steps.jsonl").read_text(encoding="utf-8")


def test_blocked_and_parse_failed_steps(ran) -> None:
    blocked, broken = ran["steps"][1], ran["steps"][2]

    assert blocked["blocked"] == {"is": True, "reason": "domain"}
    assert blocked["result"]["error_code"] == "DOMAIN_BLOCKED"
    assert blocked["result"]["url_after"] == blocked["url"] == ran["target"]  # 페이지 그대로
    assert blocked["latency_ms"]["browser"] == 0
    assert len(ran["audits"].rows) == 1

    assert broken["action"] is None
    assert broken["reasoning"] is None
    assert broken["blocked"] == {"is": True, "reason": "parse_failed"}
    assert broken["result"]["error_code"] == "PARSE_FAILED"


def test_navigation_and_done(ran) -> None:
    inside, done = ran["steps"][3], ran["steps"][4]

    assert inside["result"]["url_after"] == f"{ran['target']}?page=2"
    assert inside["task"] == {"url_reached": True}
    assert ran["steps"][0]["task"] == {"url_reached": False}
    assert done["action"]["kind"] == "done"
    assert done["blocked"] == {"is": False, "reason": None}
    assert done["result"]["error_code"] is None


# 그림 속 점의 색(RGB)을 읽는다. <img> 를 canvas 에 그려 그 점의 픽셀을 본다.
PIXEL_JS = """async ([x, y]) => {
    const img = document.getElementById('shot');
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    return Array.from(ctx.getImageData(x, y, 1, 1).data.slice(0, 3));
}"""


async def pixel_colors(browser, png: bytes, points: list[list[int]]) -> list[list[int]]:
    """찍힌 그림을 새 페이지에 띄워 각 점의 색을 읽는다."""
    viewer = await browser.new_page()
    encoded = base64.b64encode(png).decode()
    await viewer.set_content(f'<img id="shot" src="data:image/png;base64,{encoded}">')
    return [await viewer.evaluate(PIXEL_JS, point) for point in points]


def test_dom_screenshot_masks_typed_input(fixture_server: str) -> None:
    async def run() -> tuple[list[int], list[int]]:
        async with DomDriver() as driver:
            await driver.start(f"{fixture_server}/{PAGE}")
            first = await driver.observe()
            await driver.act(Action(kind="type", element_id=8, value="W" * 40))
            observation = await driver.observe()
            box = await driver._page.locator("[name=q]").bounding_box()
            # 찍힌 그림 속 입력칸 가운데 · 바깥 점의 색을 읽는다.
            inside, outside = await pixel_colors(
                driver._browser,
                observation.screenshot,
                [[int(box["x"] + 5), int(box["y"] + box["height"] / 2)], [1, 1]],
            )
            assert first.screenshot is not None
            return inside, outside

    inside, outside = asyncio.run(run())

    mask = [int(MASK_COLOR[i : i + 2], 16) for i in (1, 3, 5)]
    assert inside == mask
    assert outside != mask


@pytest.mark.parametrize("ran", [(REPLIES[:1], 1)], indirect=True)
def test_last_screen_after_step_limit_is_saved_and_masked(ran) -> None:
    # step 상한 1 로 끝난다. 마지막 행동이 입력이라 마지막 화면(step-2)은 값이 찍힌 직후의 화면이다.
    # 로그 줄은 1 개이고 step-2 에는 줄이 없다.
    folder = ran["folder"]

    assert [s["step"] for s in ran["steps"]] == [1]
    assert ran["personas"].statuses == {PERSONA_ID: "max_steps"}
    assert sorted(p.name for p in folder.iterdir()) == ["step-1.png", "step-2.png", "steps.jsonl"]
    final = (folder / "step-2.png").read_bytes()
    assert final.startswith(PNG_SIGNATURE)

    async def input_color() -> list[int]:
        # 마지막 화면을 찍은 쪽과 같은 페이지를 새 브라우저로 열어 입력칸 자리를 구한다.
        async with DomDriver() as driver:
            await driver.start(ran["target"])
            box = await driver._page.locator("[name=q]").bounding_box()
            point = [int(box["x"] + 5), int(box["y"] + box["height"] / 2)]
            return (await pixel_colors(driver._browser, final, [point]))[0]

    assert asyncio.run(input_color()) == [int(MASK_COLOR[i : i + 2], 16) for i in (1, 3, 5)]
