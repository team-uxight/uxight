"""Persona 의 도달 여부 모으기 (GACA-160). 실제 파일에 쓰고 읽는다."""

import pytest

from uxight_agent.watcher.step_log_writer import StepLogWriter

RUN_ID = 7
PERSONA_ID = 3


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([False, True, False], True),  # 한 번이라도 닿으면 닿음이다
        ([None, False], False),
        ([None, None], None),  # 판정 기록이 없으면 판정 안 함이다
        ([], None),
    ],
)
def test_url_reached_from_all_steps(tmp_path, values: list, expected: bool | None) -> None:
    writer = StepLogWriter(str(tmp_path))
    writer.prepare(RUN_ID, PERSONA_ID)
    for value in values:
        writer.append(RUN_ID, PERSONA_ID, {"task": {"url_reached": value}})

    assert writer.get_url_reached(RUN_ID, PERSONA_ID) is expected


def test_url_reached_without_log_file(tmp_path) -> None:
    assert StepLogWriter(str(tmp_path)).get_url_reached(RUN_ID, PERSONA_ID) is None
