"""DB 엔진 시간 상한 (GACA-110 리뷰 M4). 엔진만 만들고 실제 DB 에는 연결하지 않는다."""

import pytest
from sqlalchemy import event

from uxight_agent.db import create_db_engine

TIMEOUTS = {"connect_timeout": 3, "read_timeout": 10, "write_timeout": 10}


class StopBeforeConnect(Exception):
    pass


def driver_connect_params(db_url: str) -> dict:
    # 엔진이 DB 드라이버의 connect() 에 넘길 인자를 가로채고, 실제 연결 전에 멈춘다.
    engine = create_db_engine(db_url)
    params: dict = {}

    @event.listens_for(engine, "do_connect")
    def capture(dialect, conn_rec, cargs, cparams) -> None:
        params.update(cparams)
        raise StopBeforeConnect

    with pytest.raises(StopBeforeConnect):
        engine.connect()
    return params


def test_mysql_engine_has_timeouts() -> None:
    params = driver_connect_params("mysql+pymysql://u:p@127.0.0.1:3306/uxight")

    assert {key: params.get(key) for key in TIMEOUTS} == TIMEOUTS


def test_sqlite_engine_has_no_timeouts() -> None:
    params = driver_connect_params("sqlite://")

    assert not TIMEOUTS.keys() & params.keys()
