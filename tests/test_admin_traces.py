"""Admin planner-trace tests (V2): per-turn persistence, backend recording,
error traces, conversation filtering and pagination.

Run:  python -m pytest tests/test_admin_traces.py -v
"""

import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_admin.db"
os.environ["MODEL_REGISTRY_DIR"] = "ml/model_registry"
os.environ["CALIBRATION_STORE_DIR"] = "ml/model_registry/calibration"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services")))

import asyncio

import pytest
from fastapi.testclient import TestClient

from database.session import create_engine, create_session_factory, init_db
from ml.datasets.seed_db import seed


@pytest.fixture(scope="module")
def client():
    db_file = os.environ["DATABASE_URL"].rsplit("/", 1)[-1]
    if os.path.exists(db_file):
        os.remove(db_file)
    engine = create_engine(os.environ["DATABASE_URL"])
    asyncio.get_event_loop().run_until_complete(init_db(engine))
    factory = create_session_factory(engine)
    asyncio.get_event_loop().run_until_complete(
        seed(factory(), products=2, days=180, obs_per_day=2)
    )

    from api.main import app
    from api import dependencies

    with TestClient(app) as c:
        yield c
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    asyncio.get_event_loop().run_until_complete(dependencies.engine.dispose())


def _chat(client, message: str, conversation_id: str) -> dict:
    resp = client.post(
        "/chat", json={"message": message, "conversation_id": conversation_id}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _traces(client, conversation_id: str, **params) -> dict:
    resp = client.get("/admin/traces", params={"conversation_id": conversation_id, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_full_decision_turn_is_traced(client):
    conv = "trace-conv-1"
    data = _chat(client, "should I buy Sony WH-1000XM6?", conv)
    assert data["reply"]

    page = _traces(client, conv)
    assert page["total"] == 1
    t = page["items"][0]
    assert t["conversation_id"] == conv
    assert t["turn_index"] == 1
    assert t["intent"] == "SHOULD_I_BUY"
    assert t["backend"] == "deterministic"
    assert t["requires"] == ["SEARCH", "COMPARE", "HISTORY", "FORECAST", "DECIDE"]
    assert [c["tool"] for c in t["tool_calls"]] == [
        "search_products",
        "compare_offers",
        "get_price_history",
        "forecast_price",
        "get_buy_wait_decision",
    ]
    assert t["tool_calls"][0]["arguments"]["query"]
    assert len(t["steps"]) == len(t["tool_calls"])
    assert t["steps"][0]["kind"] == "search"
    assert t["error"] is None
    assert t["latency_ms"] >= 0
    assert t["reply"] == data["reply"]


def test_consecutive_turns_increment_turn_index(client):
    conv = "trace-conv-2"
    _chat(client, "cheapest Sony headphones", conv)
    _chat(client, "should I buy it now?", conv)

    page = _traces(client, conv)
    assert page["total"] == 2
    turns = [t["turn_index"] for t in page["items"]]
    assert sorted(turns) == [1, 2]
    assert page["items"][0]["turn_index"] == 2  # newest first
    assert page["items"][0]["intent"] == "SHOULD_I_BUY"
    assert page["items"][1]["requires"] == ["SEARCH", "COMPARE"]


def test_failed_search_turn_is_traced_with_error(client):
    conv = "trace-conv-3"
    data = _chat(client, "should I buy the NoSuchGadget ZX9000 Pro?", conv)
    assert "couldn't complete" in data["reply"]

    page = _traces(client, conv)
    assert page["total"] == 1
    t = page["items"][0]
    assert t["error"]
    assert [c["tool"] for c in t["tool_calls"]] == ["search_products"]
    assert t["steps"][0]["kind"] == "search"
    assert t["intent"] == "SHOULD_I_BUY"


def test_pagination_and_conversation_isolation(client):
    conv_a = "trace-conv-a"
    conv_b = "trace-conv-b"
    _chat(client, "cheapest Sony headphones", conv_a)
    _chat(client, "cheapest Sony headphones", conv_b)

    a_page = _traces(client, conv_a, limit=1)
    assert a_page["total"] == 1
    assert len(a_page["items"]) == 1

    b_page = _traces(client, conv_b)
    assert b_page["total"] == 1
    assert b_page["items"][0]["conversation_id"] == conv_b

    all_page = client.get("/admin/traces", params={"limit": 10}).json()
    assert all_page["total"] >= 5
    assert len(all_page["items"]) == all_page["total"]


def test_trace_by_id_and_404(client):
    conv = "trace-conv-4"
    _chat(client, "cheapest Sony headphones", conv)
    trace_id = _traces(client, conv)["items"][0]["id"]

    resp = client.get(f"/admin/traces/{trace_id}")
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == conv

    resp = client.get("/admin/traces/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404