"""GACA-169: 시험 적용 실패 필터링 및 재생성 통합 테스트."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from uxight_agent.watcher import run_orchestrator as module
from uxight_agent.watcher.run_orchestrator import RunOrchestrator

URL = "https://school.example.com/student"


def make_options():
    return [
        {
            "option_no": number,
            "finding_ids": [1],
            "patch_kind": "relabel",
            "patch": {
                "target": f"#item{number}",
                "new_text": f"개선 문구 {number}",
                "page_url": URL,
            },
            "rationale": "탐색 개선",
            "expected_effect": "탐색 단계 감소",
            "fix_cost": None,
        }
        for number in (1, 2, 3)
    ]


async def run_trial(monkeypatch, rejected, expected_attempts):
    saved = []
    attempts = []
    trials = []

    findings = [{"finding_id": 1}]

    monkeypatch.setattr(
        module.finding_repository,
        "get_by_run",
        lambda run_id: findings,
    )
    monkeypatch.setattr(
        module,
        "select_improvement_evidence",
        lambda items, hosts: (URL, items),
    )
    monkeypatch.setattr(
        module.improvement_repository,
        "insert_all",
        lambda run_id, rows: saved.append((run_id, rows)),
    )
    monkeypatch.setattr(module, "llm_client", lambda: object())

    async def fake_generate(**kwargs):
        attempts.append(1)
        return make_options()

    monkeypatch.setattr(
        module,
        "generate_improvements",
        fake_generate,
    )

    @asynccontextmanager
    async def fake_open_driver(self, run_id, persona_id, hosts):
        yield SimpleNamespace(page=SimpleNamespace(url=URL))

    async def fake_open_page(self, driver, url, hosts):
        assert url == URL

    async def fake_validate(page, kind, patch):
        target = patch["target"]
        trials.append(target)
        assert "page_url" not in patch

        if target in rejected:
            return False, "Trial patch rejected"

        return True, None

    monkeypatch.setattr(RunOrchestrator, "_open_driver", fake_open_driver)
    monkeypatch.setattr(RunOrchestrator, "_open_improvement_page", fake_open_page)
    monkeypatch.setattr(
        module,
        "validate_patch_application",
        fake_validate,
    )

    snapshot = SimpleNamespace(
        target_url=URL,
        allowed_domains=[],
        task={"goal": "장학금 찾기"},
    )

    await RunOrchestrator()._save_improvements(1, snapshot)

    assert len(attempts) == expected_attempts
    return saved, trials


def test_partial_trial_failure_keeps_valid_options(monkeypatch):
    saved, trials = asyncio.run(run_trial(monkeypatch, {"#item2"}, 1))

    assert len(trials) == 3
    assert len(saved) == 1

    rows = saved[0][1]

    assert len(rows) == 2
    assert [row["option_no"] for row in rows] == [1, 2]
    assert [row["patch"]["target"] for row in rows] == [
        "#item1",
        "#item3",
    ]
    assert all(row["patch"]["page_url"] == URL for row in rows)


def test_all_trials_failed_retries_once(monkeypatch):
    saved, trials = asyncio.run(
        run_trial(
            monkeypatch,
            {"#item1", "#item2", "#item3"},
            2,
        )
    )

    assert len(trials) == 6
    assert saved == []
