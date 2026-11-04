"""단일 vs 다중 진단 비교 CLI (GACA-181). benchmark 결과 폴더 모양으로 예시 회차 9001 을 돌린다."""

import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import FIXTURES

from uxight_agent import bench, bench_diagnose, bench_metrics
from uxight_agent.persona.llm_decider import LLMDecider

RUN_DIR = FIXTURES / "runs" / "9001"
# 회차 1 은 원본 사본, 회차 2 는 결함 사본으로 쓴다.
RUNS = {1: "original", 2: "seedA"}
NAV_PAGE = "/kor/1104/subview.do"  # Persona 2 길 찾기 혼란의 근거 url 경로


def agree(body: dict) -> str:
    rules = body["messages"][1]["content"].split("## 행동 로그")[0]
    checks = [
        {"finding_id": int(n), "correct": True, "summary": f"요약 {n}"}
        for n in re.findall(r'"finding_id": (\d+)', rules)
    ]
    return json.dumps({"rule_checks": checks, "findings": []}, ensure_ascii=False)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) + "\n" for row in rows]
    path.write_text("".join(lines), encoding="utf-8")


@pytest.fixture
def bench_dir(tmp_path: Path) -> Path:
    """benchmark 가 남긴 것과 같은 모양의 폴더(personas.jsonl · steps.jsonl)."""
    run = json.loads((RUN_DIR / "run.json").read_text(encoding="utf-8"))
    folder = tmp_path / "bench"
    folder.mkdir()
    records, steps = [], []
    for run_id, site in RUNS.items():
        for persona in run["personas"]:
            number = persona["persona_id"]
            persona_id = f"P{number:03d}"  # benchmark 의 Persona id 는 글자다
            lines = (RUN_DIR / str(number) / "steps.jsonl").read_text(encoding="utf-8")
            change = {"run_id": run_id, "persona_id": persona_id}
            log = [json.loads(line) | change for line in lines.splitlines()]
            steps += log
            records.append(
                {
                    "run_id": run_id,
                    "variant": "dom",
                    "site": site,
                    "task": 1,
                    "repeat": 1,
                    "persona_id": persona_id,
                    "outcome": persona["status"],
                    **bench_metrics.persona_measures(log),
                }
            )
    write_jsonl(folder / "personas.jsonl", records)
    write_jsonl(folder / "steps.jsonl", steps)
    return folder


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LLM_PRICES", '{"test-model": [1.0, 2.0]}')
    monkeypatch.setenv("BENCH_COMMIT", "abc1234")
    (tmp_path / "personas.json").write_text("[]", encoding="utf-8")
    answers = {
        "injected": [
            {"catalog_id": "NAV-L", "page": NAV_PAGE},
            {"catalog_id": "INT-L", "page": "/없는/쪽.do"},
            {"catalog_id": "DST-ALT", "page": "*"},  # 구현 4종이 아니라 세지 않는다
        ]
    }
    (tmp_path / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    path = tmp_path / "bench.json"
    settings = {
        "name": "시험",
        "personas_file": "personas.json",
        "personas": ["P001"],
        "tasks": [{"goal": "찾기", "success_rule": "닿는다", "success_url": "/a"}],
        "sites": [
            {"name": "original", "url": "/kor/index.do", "original": True},
            {"name": "seedA", "url": "/kor/index.do", "answers": "answers.json"},
        ],
        "variants": {"dom": {}},
        "max_steps": 15,
        "max_seconds": 60,
    }
    path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    return path


def argv(config: Path, bench_dir: Path, out: Path, *extra: str) -> list[str]:
    return [str(config), "--bench", str(bench_dir), "--out", str(out), *extra]


def table_row(md: str, mode: str, name: str, site: str) -> list[str]:
    (line,) = [
        x for x in md.splitlines() if x.startswith(f"| {mode} | {name} |") and f"| {site} |" in x
    ]
    return [cell.strip() for cell in line.strip("|").split("|")]


@pytest.fixture
def ran(scripted_llm, config: Path, bench_dir: Path, tmp_path: Path) -> dict:
    llm, requests = scripted_llm(answer=agree)
    out = tmp_path / "out"
    extra = ("--mode", "single", "--mode", "multi", "--min-personas", "2")

    assert bench_diagnose.main(argv(config, bench_dir, out, *extra), llm=llm) == 0

    return {"out": out, "requests": requests, "md": (out / "summary.md").read_text("utf-8")}


def test_one_log_is_measured_both_ways(ran: dict) -> None:
    # 회차 2개: 단일은 회차마다 1번, 다중은 판정한 Persona 4명마다 1번이다.
    assert len(ran["requests"]) == 2 * (1 + 4)
    for mode in ("single", "multi"):
        for run_id in RUNS:
            folder = ran["out"] / mode / str(run_id)
            for name in ("messages.jsonl", "rule-findings.json", "findings.json"):
                assert (folder / name).is_file()
            assert (folder / "findings-filtered.json").is_file()
            assert (folder / "P001" / "steps.jsonl").is_file()


def test_assignment_paths_point_at_real_logs(ran: dict) -> None:
    root = ran["out"] / "multi"
    lines = (root / "2" / "messages.jsonl").read_text(encoding="utf-8").splitlines()
    assigns = [json.loads(x) for x in lines if '"act": "assign"' in x]

    assert len(assigns) == 4
    for message in assigns:
        (path,) = message["content"]["step_logs"]
        steps = [json.loads(x) for x in (root / path).read_text(encoding="utf-8").splitlines()]
        assert {s["run_id"] for s in steps} == {2}
    rules = json.loads((root / "2" / "rule-findings.json").read_text(encoding="utf-8"))
    assert [r["finding_id"] for r in rules] == list(range(1, 8))


def test_findings_go_straight_into_recall_counts(ran: dict) -> None:
    folder = ran["out"] / "multi" / "2"
    union = json.loads((folder / "findings.json").read_text(encoding="utf-8"))
    filtered = json.loads((folder / "findings-filtered.json").read_text(encoding="utf-8"))
    answers = {"injected": [{"catalog_id": "NAV-L", "page": NAV_PAGE}]}

    assert bench_metrics.recall_counts(union, answers) == (1, 1)
    assert all(set(f) == {"taxonomy", "severity", "summary", "evidence"} for f in union)
    assert all(len({e["persona_id"] for e in f["evidence"]}) >= 2 for f in filtered)
    assert 0 < len(filtered) < len(union)


def test_table_has_recall_false_positives_and_totals(ran: dict) -> None:
    md = ran["md"]
    columns = bench_diagnose.COLUMNS
    union = dict(zip(columns, table_row(md, "multi", "합집합", "seedA"), strict=True))
    filtered = dict(zip(columns, table_row(md, "multi", "근거 수 2명", "seedA"), strict=True))
    original = dict(zip(columns, table_row(md, "single", "합집합", "original"), strict=True))

    assert union["재현율"] == "50% (1/2)"  # 구현 4종 2개 중 NAV-L 만 맞혔다
    assert union["오탐"] == "—"
    assert original["재현율"] == "—"
    assert int(original["오탐"]) == int(original["진단 수"]) > 0  # 원본의 진단은 모두 오탐이다
    assert int(filtered["진단 수"]) < int(union["진단 수"])
    # 합계: 답 하나 = 입력 11 · 출력 7 토큰. 회차 하나를 다중으로 돌리면 호출 4번이다.
    assert (union["배정"], union["다시 배정"], union["진단 없이 마감"]) == ("4", "0", "0")
    assert (union["입력 토큰"], union["출력 토큰"]) == ("44", "28")
    assert float(union["비용($)"]) == pytest.approx(0.0001)  # 4 × (11 × $1 + 7 × $2) / 100만
    assert original["입력 토큰"] == "11"
    assert union["걸린 시간(s)"] != ""


def test_summary_records_conditions(ran: dict) -> None:
    md = ran["md"]

    assert "- 커밋: abc1234" in md
    assert "- 모델: test-model" in md
    assert "근거 url 이 1개 이상 겹침" in md
    assert "Persona 2명 이상" in md


def test_usage_stays_in_the_result_folder(ran: dict, tmp_path: Path) -> None:
    lines = (ran["out"] / "usage.jsonl").read_text(encoding="utf-8").splitlines()
    roles = sorted({json.loads(x)["role"] for x in lines})

    assert roles == ["diagnoser_multi", "diagnoser_single"]
    assert len(lines) == len(ran["requests"])
    assert not (tmp_path / "llm-usage.jsonl").exists()
    assert os.environ["LLM_USAGE_LOG"] == str(tmp_path / "llm-usage.jsonl")


def test_runs_on_what_bench_really_writes(
    scripted_llm, fixture_server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 진짜 드라이버로 돈 benchmark 결과 폴더를 그대로 받는다. 이어지는 자리가 어긋나지 않는지 본다.
    monkeypatch.setenv("BENCH_COMMIT", "abc1234")
    page = f"{fixture_server}/domain_links.html"
    persona = {"persona_id": "P001", "name": "계층 우선", "web_skill": "low"}
    (tmp_path / "personas.json").write_text(json.dumps([persona]), encoding="utf-8")
    settings = {
        "name": "시험",
        "personas_file": "personas.json",
        "personas": ["P001"],
        "tasks": [{"goal": "찾기", "success_rule": "닿는다", "success_url": "/none.html"}],
        "sites": [{"name": "original", "url": page, "original": True}],
        "variants": {"dom": {}},
        "max_steps": 2,
        "max_seconds": 60,
    }
    config = tmp_path / "bench.json"
    config.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    scroll = {"kind": "scroll", "element_id": None, "value": "down"}
    step = json.dumps({"reasoning": "내려 본다", "action": scroll}, ensure_ascii=False)
    runner, _ = scripted_llm(step, step)
    bench_dir, out = tmp_path / "bench", tmp_path / "out"
    assert (
        bench.main(
            [str(config), "--out", str(bench_dir)],
            make_decider=functools.partial(LLMDecider, runner),
        )
        == 0
    )

    def answer(body: dict) -> str:
        spot = {"persona_id": "P001", "step_from": 1, "step_to": 2, "url": "http://지어낸/"}
        found = {"taxonomy": "interaction_failure", "summary": "놓친 문제", "evidence": [spot]}
        return json.dumps(json.loads(agree(body)) | {"findings": [found]}, ensure_ascii=False)

    llm, requests = scripted_llm(answer=answer)
    assert bench_diagnose.main(argv(config, bench_dir, out, "--mode", "multi"), llm=llm) == 0

    assert len(requests) == 1
    rows = json.loads((out / "multi" / "1" / "findings.json").read_text(encoding="utf-8"))
    # 규칙이 잡은 과제 실패(맞음으로 표시)와 진단자가 더한 조작 실패다.
    assert [r["taxonomy"] for r in rows] == ["task_failure", "interaction_failure"]
    assert rows[1]["evidence"] == [
        {"persona_id": "P001", "step_from": 1, "step_to": 2, "url": page}
    ]


def test_one_mode_can_run_alone_with_its_settings(
    scripted_llm, config: Path, bench_dir: Path, tmp_path: Path
) -> None:
    llm, requests = scripted_llm(answer=agree)
    out = tmp_path / "out"
    extra = ("--mode", "multi", "--mode", "multi", "--min-personas", "3", "--min-shared-urls", "2")

    assert bench_diagnose.main(argv(config, bench_dir, out, *extra), llm=llm) == 0

    assert len(requests) == 2 * 4  # 같은 값을 두 번 줘도 한 번만 돈다
    assert not (out / "single").exists()
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "근거 url 이 2개 이상 겹침" in md
    assert table_row(md, "multi", "근거 수 3명", "seedA")


def test_closed_personas_are_counted_per_persona(
    scripted_llm, config: Path, bench_dir: Path, tmp_path: Path
) -> None:
    llm, _ = scripted_llm(answer=lambda body: "보고 없음")
    out = tmp_path / "out"

    assert bench_diagnose.main(argv(config, bench_dir, out, "--mode", "single"), llm=llm) == 0

    md = (out / "summary.md").read_text(encoding="utf-8")
    row = dict(zip(bench_diagnose.COLUMNS, table_row(md, "single", "합집합", "seedA"), strict=True))
    assert (row["배정"], row["다시 배정"], row["진단 없이 마감"]) == ("2", "1", "4")
    assert row["진단 수"] == "0"


def test_persona_without_steps_is_not_assigned(
    scripted_llm, config: Path, bench_dir: Path, tmp_path: Path
) -> None:
    # 브라우저가 뜨기 전에 끝난 실행은 step 로그가 없다.
    path = bench_dir / "personas.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0]) | {"persona_id": "P006", "outcome": "max_steps"}
    write_jsonl(path, [*map(json.loads, lines), record])
    llm, requests = scripted_llm(answer=agree)
    out = tmp_path / "out"

    assert bench_diagnose.main(argv(config, bench_dir, out, "--mode", "multi"), llm=llm) == 0

    assert len(requests) == 2 * 4


@pytest.mark.parametrize("missing", ["personas.jsonl", "steps.jsonl"])
def test_bench_folder_must_have_the_logs(
    scripted_llm, config: Path, bench_dir: Path, tmp_path: Path, missing: str
) -> None:
    (bench_dir / missing).unlink()
    llm, requests = scripted_llm(answer=agree)

    with pytest.raises(SystemExit):
        bench_diagnose.main(argv(config, bench_dir, tmp_path / "out", "--mode", "multi"), llm=llm)

    assert requests == []


def test_site_must_be_in_the_config(
    scripted_llm, config: Path, bench_dir: Path, tmp_path: Path, capsys
) -> None:
    settings = json.loads(config.read_text(encoding="utf-8"))
    settings["sites"].pop()
    config.write_text(json.dumps(settings), encoding="utf-8")
    llm, requests = scripted_llm(answer=agree)

    with pytest.raises(SystemExit):
        bench_diagnose.main(argv(config, bench_dir, tmp_path / "out", "--mode", "multi"), llm=llm)

    assert "seedA" in capsys.readouterr().err
    assert requests == []


def test_out_folder_must_be_empty(
    scripted_llm, config: Path, bench_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "x").write_text("", encoding="utf-8")
    llm, requests = scripted_llm(answer=agree)

    with pytest.raises(SystemExit):
        bench_diagnose.main(argv(config, bench_dir, out, "--mode", "multi"), llm=llm)

    assert requests == []


def test_mode_is_required_and_limited(config: Path, bench_dir: Path, tmp_path: Path) -> None:
    for extra in ((), ("--mode", "both")):
        with pytest.raises(SystemExit):
            bench_diagnose.main(argv(config, bench_dir, tmp_path / "out", *extra))


def test_llm_settings_are_required(
    config: Path, bench_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit):
        bench_diagnose.main(argv(config, bench_dir, tmp_path / "out", "--mode", "multi"))

    assert "LLM 설정" in capsys.readouterr().err


def test_never_loads_the_db_module() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("DB_URL", "LOG_DIR")}
    code = "import sys, uxight_agent.bench_diagnose; sys.exit('uxight_agent.db' in sys.modules)"
    subprocess.run([sys.executable, "-c", code], env=env, check=True)
