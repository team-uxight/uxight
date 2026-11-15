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
        "improvement_evidence_pages",
        lambda items, hosts: [(URL, items)],
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


def test_page_without_options_moves_to_next_evidence_page(monkeypatch):
    """회차 32: 근거 수가 같은 두 페이지 중 앞 페이지(사본에 없는 페이지)에서 안이 나오지 않으면
    다음 근거 페이지로 넘어가 거기서 나온 안을 저장한다."""
    missing = "https://school.example.com/kor/3120/subview.do"
    answer = "https://school.example.com/kor/12490/subview.do"
    findings = [
        {"finding_id": 18, "evidence": [{"url": missing}]},
        {"finding_id": 19, "evidence": [{"url": answer}]},
    ]
    saved = []
    generated_on = []

    monkeypatch.setattr(module.finding_repository, "get_by_run", lambda run_id: findings)
    monkeypatch.setattr(
        module.improvement_repository,
        "insert_all",
        lambda run_id, rows: saved.append((run_id, rows)),
    )
    monkeypatch.setattr(module, "llm_client", lambda: object())

    async def fake_generate(**kwargs):
        page_url = kwargs["page"].url
        generated_on.append((page_url, [f["finding_id"] for f in kwargs["findings"]]))
        if page_url == missing:
            return []
        return [
            {
                "option_no": 1,
                "finding_ids": [19],
                "patch_kind": "relabel",
                "patch": {
                    "target": "#title",
                    "new_text": "졸업 이수학점 기준표",
                    "page_url": page_url,
                },
                "rationale": "답 페이지 제목이 무엇의 표인지 알려 주지 않는다.",
                "expected_effect": "탐색 단계 감소",
                "fix_cost": None,
            }
        ]

    monkeypatch.setattr(module, "generate_improvements", fake_generate)

    @asynccontextmanager
    async def fake_open_driver(self, run_id, persona_id, hosts):
        yield SimpleNamespace(page=SimpleNamespace(url=None))

    async def fake_open_page(self, driver, url, hosts):
        driver.page.url = url

    async def fake_validate(page, kind, patch):
        return True, None

    monkeypatch.setattr(RunOrchestrator, "_open_driver", fake_open_driver)
    monkeypatch.setattr(RunOrchestrator, "_open_improvement_page", fake_open_page)
    monkeypatch.setattr(module, "validate_patch_application", fake_validate)

    snapshot = SimpleNamespace(
        target_url="https://school.example.com/",
        allowed_domains=[],
        task={"goal": "26학번 졸업 이수학점 기준 찾기"},
    )

    asyncio.run(RunOrchestrator()._save_improvements(32, snapshot))

    assert generated_on == [(missing, [18]), (missing, [18]), (answer, [19])]
    assert len(saved) == 1
    assert saved[0][0] == 32
    assert [row["patch"]["page_url"] for row in saved[0][1]] == [answer]
    assert [row["option_no"] for row in saved[0][1]] == [1]


def test_no_page_with_options_saves_nothing(monkeypatch):
    """어느 근거 페이지에서도 안이 나오지 않으면 페이지마다 두 번 시도하고 저장하지 않는다."""
    first = "https://school.example.com/a"
    second = "https://school.example.com/b"
    findings = [
        {"finding_id": 1, "evidence": [{"url": first}]},
        {"finding_id": 2, "evidence": [{"url": second}]},
    ]
    saved = []
    generated_on = []

    monkeypatch.setattr(module.finding_repository, "get_by_run", lambda run_id: findings)
    monkeypatch.setattr(
        module.improvement_repository,
        "insert_all",
        lambda run_id, rows: saved.append((run_id, rows)),
    )
    monkeypatch.setattr(module, "llm_client", lambda: object())

    async def fake_generate(**kwargs):
        generated_on.append(kwargs["page"].url)
        return []

    monkeypatch.setattr(module, "generate_improvements", fake_generate)

    @asynccontextmanager
    async def fake_open_driver(self, run_id, persona_id, hosts):
        yield SimpleNamespace(page=SimpleNamespace(url=None))

    async def fake_open_page(self, driver, url, hosts):
        driver.page.url = url

    monkeypatch.setattr(RunOrchestrator, "_open_driver", fake_open_driver)
    monkeypatch.setattr(RunOrchestrator, "_open_improvement_page", fake_open_page)

    snapshot = SimpleNamespace(
        target_url="https://school.example.com/",
        allowed_domains=[],
        task={"goal": "장학금 찾기"},
    )

    asyncio.run(RunOrchestrator()._save_improvements(1, snapshot))

    assert generated_on == [first, first, second, second]
    assert saved == []


def test_missing_page_is_skipped_without_llm(monkeypatch, fixture_server, caplog):
    """사본에 없는 페이지(404)는 LLM 을 부르지 않고 다음 근거 페이지로 넘어간다.
    실제 브라우저로 404 를 받아 본다."""
    missing = f"{fixture_server}/no-such-page.html"
    present = f"{fixture_server}/body_text.html"
    findings = [
        {"finding_id": 1, "evidence": [{"url": missing}]},
        {"finding_id": 2, "evidence": [{"url": present}]},
    ]
    saved = []
    generated_on = []

    monkeypatch.setattr(module.finding_repository, "get_by_run", lambda run_id: findings)
    monkeypatch.setattr(
        module.improvement_repository,
        "insert_all",
        lambda run_id, rows: saved.append((run_id, rows)),
    )
    monkeypatch.setattr(module, "llm_client", lambda: object())

    async def fake_generate(**kwargs):
        page_url = kwargs["page"].url
        generated_on.append(page_url)
        return [
            {
                "option_no": 1,
                "finding_ids": [2],
                "patch_kind": "highlight",
                "patch": {"target": "body", "style": "outline", "page_url": page_url},
                "rationale": "근거 페이지에서 찾기 어려웠다.",
                "expected_effect": "탐색 단계 감소",
                "fix_cost": None,
            }
        ]

    async def fake_validate(page, kind, patch):
        return True, None

    monkeypatch.setattr(module, "generate_improvements", fake_generate)
    monkeypatch.setattr(module, "validate_patch_application", fake_validate)
    caplog.set_level("INFO", logger="uxight_agent.watcher.run_orchestrator")

    snapshot = SimpleNamespace(
        target_url=fixture_server,
        allowed_domains=[],
        task={"goal": "장학금 찾기"},
    )

    asyncio.run(RunOrchestrator()._save_improvements(5, snapshot))

    assert generated_on == [present]
    assert [row["patch"]["page_url"] for row in saved[0][1]] == [present]
    assert any(
        r.levelname == "INFO" and missing in r.getMessage() and "404" in r.getMessage()
        for r in caplog.records
    )


def test_error_on_one_page_moves_to_next_evidence_page(monkeypatch, caplog):
    """한 페이지에서 예외(LLM JSON 오류 등)가 나도 개선안 단계를 끝내지 않고 다음 페이지를 본다."""
    broken = "https://school.example.com/a"
    good = "https://school.example.com/b"
    findings = [
        {"finding_id": 1, "evidence": [{"url": broken}]},
        {"finding_id": 2, "evidence": [{"url": good}]},
    ]
    saved = []
    generated_on = []

    monkeypatch.setattr(module.finding_repository, "get_by_run", lambda run_id: findings)
    monkeypatch.setattr(
        module.improvement_repository,
        "insert_all",
        lambda run_id, rows: saved.append((run_id, rows)),
    )
    monkeypatch.setattr(module, "llm_client", lambda: object())

    async def fake_generate(**kwargs):
        page_url = kwargs["page"].url
        generated_on.append(page_url)
        if page_url == broken:
            raise ValueError("Invalid improvement response JSON")
        return [
            {
                "option_no": 1,
                "finding_ids": [2],
                "patch_kind": "relabel",
                "patch": {"target": "#menu", "new_text": "장학금 신청", "page_url": page_url},
                "rationale": "메뉴 이름이 불명확하다.",
                "expected_effect": "탐색 단계 감소",
                "fix_cost": None,
            }
        ]

    monkeypatch.setattr(module, "generate_improvements", fake_generate)

    @asynccontextmanager
    async def fake_open_driver(self, run_id, persona_id, hosts):
        yield SimpleNamespace(page=SimpleNamespace(url=None))

    async def fake_open_page(self, driver, url, hosts):
        driver.page.url = url

    async def fake_validate(page, kind, patch):
        return True, None

    monkeypatch.setattr(RunOrchestrator, "_open_driver", fake_open_driver)
    monkeypatch.setattr(RunOrchestrator, "_open_improvement_page", fake_open_page)
    monkeypatch.setattr(module, "validate_patch_application", fake_validate)

    snapshot = SimpleNamespace(
        target_url="https://school.example.com/",
        allowed_domains=[],
        task={"goal": "장학금 찾기"},
    )

    asyncio.run(RunOrchestrator()._save_improvements(6, snapshot))

    assert generated_on == [broken, good]
    assert [row["patch"]["page_url"] for row in saved[0][1]] == [good]
    assert any(r.levelname == "ERROR" and broken in r.getMessage() for r in caplog.records)
