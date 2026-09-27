"""Realtime data-layer tests: sequence, envelope, hub filtering, emitters."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_realtime.db")
os.environ.setdefault("MODEL_REGISTRY_DIR", "ml/model_registry")
os.environ.setdefault("CALIBRATION_STORE_DIR", "ml/model_registry/calibration")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services")))

import pytest

from events.bus import BaseEvent, EventBus
from api.realtime import (
    RealtimeConnection,
    RealtimeHub,
    aggregate_of,
    build_envelope,
)

NOW = datetime.now(timezone.utc)


def _event(event_type: str, payload: dict, seq: int | None = None) -> BaseEvent:
    ev = BaseEvent(event_type=event_type, payload=payload, occurred_at=NOW)
    if seq is not None:
        ev.sequence = seq
    return ev


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False
        self._rx: asyncio.Queue[str] = asyncio.Queue()

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        return await self._rx.get()

    async def close(self) -> None:
        self.closed = True


class TestSequence:
    def test_bus_assigns_monotonic_sequence(self):
        bus = EventBus()
        got = []

        def cb(ev):
            got.append(ev.sequence)

        bus.subscribe(cb)

        async def run():
            await bus.publish(BaseEvent(event_type="price.changed", payload={}))
            await bus.publish(BaseEvent(event_type="price.changed", payload={}))

        asyncio.run(run())
        assert got == [0, 1]
        assert bus._seq == 2

    def test_explicit_sequence_preserved(self):
        bus = EventBus()
        ev = _event("price.changed", {}, seq=42)

        async def run():
            await bus.publish(ev)

        asyncio.run(run())
        assert ev.sequence == 42


class TestEnvelope:
    def test_listing_aggregate(self):
        ev = _event("price.changed", {"listing_id": "list-1"})
        env = build_envelope(ev)
        assert env["aggregate_type"] == "listing"
        assert env["aggregate_id"] == "list-1"

    def test_variant_aggregate(self):
        ev = _event("prediction.updated", {"product_variant_id": "var-1"})
        env = build_envelope(ev)
        assert env["aggregate_type"] == "product_variant"
        assert env["aggregate_id"] == "var-1"

    def test_system_fallback(self):
        env = build_envelope(_event("model.promoted", {}))
        assert env["aggregate_type"] == "system"

    def test_envelope_shape(self):
        ev = _event("price.dropped", {"listing_id": "l", "observed_at": "2026-08-01T00:00:00+00:00"})
        env = build_envelope(ev)
        for key in ("v", "event_id", "event_type", "aggregate_type", "aggregate_id", "sequence", "occurred_at", "observed_at", "payload"):
            assert key in env
        assert env["observed_at"] == "2026-08-01T00:00:00+00:00"
        assert env["sequence"] is None or isinstance(env["sequence"], int)


class TestHubFiltering:
    def test_topic_and_entity_filter(self):
        hub = RealtimeHub(EventBus())
        ws = FakeWS()
        conn = RealtimeConnection(ws, {"price.changed"}, {"list-1"})
        hub._connections.append(conn)

        hub._deliver(_event("price.changed", {"listing_id": "list-1"}))
        hub._deliver(_event("price.changed", {"listing_id": "list-2"}))
        hub._deliver(_event("stock.changed", {"listing_id": "list-1"}))
        assert conn.queue.qsize() == 1

    def test_entityless_subscription_receives_all_topics(self):
        hub = RealtimeHub(EventBus())
        ws = FakeWS()
        conn = RealtimeConnection(ws, {"price.changed", "alert.triggered"}, set())
        hub._connections.append(conn)
        hub._deliver(_event("price.changed", {"listing_id": "x"}))
        hub._deliver(_event("alert.triggered", {"product_variant_id": "v"}))
        assert conn.queue.qsize() == 2

    def test_envelopes_carry_sequence(self):
        hub = RealtimeHub(EventBus())
        ws = FakeWS()
        conn = RealtimeConnection(ws, {"price.changed"}, set())
        hub._connections.append(conn)
        hub._deliver(_event("price.changed", {"listing_id": "x"}, seq=7))
        env = conn.queue.get_nowait()
        assert env["sequence"] == 7

    def test_slow_client_drops_not_crash(self):
        hub = RealtimeHub(EventBus())
        conn = RealtimeConnection(FakeWS(), {"price.changed"}, set())
        conn.queue = asyncio.Queue(maxsize=1)
        hub._connections.append(conn)
        hub._deliver(_event("price.changed", {"listing_id": "x"}, seq=1))
        hub._deliver(_event("price.changed", {"listing_id": "x"}, seq=2))
        assert conn.queue.qsize() == 1
        assert conn.dropped == 1


class TestHandleAndHeartbeat:
    def test_hello_and_ping_pong(self):
        bus = EventBus()
        hub = RealtimeHub(bus)
        ws = FakeWS()

        async def run():
            task = asyncio.create_task(hub.handle(ws, {"price.changed"}, set()))
            await asyncio.sleep(0.05)
            assert ws.sent[0]["type"] == "hello"
            ws._rx.put_nowait('{"type": "ping"}')
            await asyncio.sleep(0.05)
            assert any(m["type"] == "pong" for m in ws.sent)
            ws._rx.put_nowait("disconnect")
            task.cancel()

        asyncio.run(run())

    def test_dynamic_subscribe(self):
        bus = EventBus()
        hub = RealtimeHub(bus)
        ws = FakeWS()
        task = None

        async def run():
            nonlocal task
            task = asyncio.create_task(hub.handle(ws, {"price.changed"}, set()))
            await asyncio.sleep(0.02)
            ws._rx.put_nowait('{"type": "subscribe", "topics": ["decision.changed"], "entities": ["v-1"]}')
            await asyncio.sleep(0.05)
            conn = hub._connections[0]
            assert "decision.changed" in conn.topics
            assert "v-1" in conn.entities
            task.cancel()

        asyncio.run(run())

    def test_start_heartbeat(self):
        bus = EventBus()
        hub = RealtimeHub(bus)

        async def run():
            await hub.start_heartbeat()
            assert hub._heartbeat_task is not None
            hub._heartbeat_task.cancel()

        asyncio.run(run())


class TestWsEndpoint:
    def test_ws_live_endpoint_smoke(self):
        from fastapi.testclient import TestClient
        from api.main import app

        if os.path.exists("test_realtime.db"):
            os.remove("test_realtime.db")
        with TestClient(app) as client:
            with client.websocket_connect("/ws/live?topics=price.changed") as ws:
                hello = ws.receive_json()
                assert hello["type"] == "hello"
                assert hello["topics"] == ["price.changed"]

                hub = client.app.state.realtime_hub
                hub._deliver(
                    _event(
                        "price.changed",
                        {"listing_id": "list-x", "from": 100.0, "to": 99.0, "retailer_name": "mock"},
                        seq=3,
                    )
                )
                env = ws.receive_json()
                assert env["v"] == 1
                assert env["event_type"] == "price.changed"
                assert env["aggregate_type"] == "listing"
                assert env["aggregate_id"] == "list-x"
                assert env["sequence"] == 3
                assert env["payload"]["to"] == 99.0


class TestEmitters:
    def test_decision_change_published_only_on_flip(self):
        from api.routes.predictions import _LAST_DECISION, _publish_decision_change

        _LAST_DECISION.clear()
        bus = EventBus()
        published: list[str] = []
        bus.subscribe(lambda ev: published.append(ev.event_type))
        variant_id = uuid.uuid4()

        class Req:
            class App:
                state = SimpleNamespace(event_bus=bus)

            app = App()

        async def run():
            await _publish_decision_change(Req(), variant_id, {"recommendation": "WAIT", "expected_saving": 100})
            await _publish_decision_change(Req(), variant_id, {"recommendation": "WAIT", "expected_saving": 100})
            await _publish_decision_change(Req(), variant_id, {"recommendation": "BUY_NOW", "expected_saving": 50})

        asyncio.run(run())
        assert published == ["decision.changed"]  # only the flip

    def test_store_prediction_publishes_updated(self):
        from api.routes.predictions import _store_prediction

        bus = EventBus()
        payloads: list[dict] = []
        bus.subscribe(lambda ev: payloads.append(ev.payload))

        class FakeF:
            horizon_hours = 720
            p50 = 26000.0
            p05 = p10 = p25 = 24000.0
            p75 = p90 = p95 = 30000.0

        class FakeResp:
            forecast = FakeF()
            interval = {"lower": 22000.0, "upper": 30000.0}
            probability_below_target = 0.42
            target_price = 25000.0
            confidence = type("C", (), {"score": 0.71})()
            model_version = "v7"
            calibration_key_used = "k"
            current_price = 27000.0
            generated_at = datetime.now(timezone.utc)

        class FakeResult:
            def scalar_one_or_none(self):
                return None

            def scalars(self):
                return self

            def all(self):
                return []

        class FakeDB:
            async def add(self, _):  # noqa: N805
                pass

            async def execute(self, _stmt):
                return FakeResult()

            async def commit(self):
                pass

        async def run():
            await _store_prediction(FakeDB(), uuid.uuid4(), FakeResp(), bus)

        asyncio.run(run())
        assert payloads and payloads[0]["horizon_hours"] == 720
        assert payloads[0]["interval_lower"] == 22000.0