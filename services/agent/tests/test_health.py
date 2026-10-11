from fastapi.testclient import TestClient

from uxight_agent.main import app
from uxight_agent.schemas import Action

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "agent"}


def test_action_schema_rejects_unknown_action() -> None:
    assert Action(kind="click", element_id=3).element_id == 3
    assert Action(kind="done").kind == "done"
    for kind in ("select", "execute_js"):
        try:
            Action(kind=kind)  # type: ignore[arg-type]
        except ValueError:
            continue
        raise AssertionError(f"unknown action must be rejected: {kind}")
