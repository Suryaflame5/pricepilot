"""Realtime hub: bridges the EventBus to WebSocket clients (V2 live data layer).

Snapshot-and-stream model:
  - REST stays the authoritative initial snapshot (client loads it first).
  - WS delivers ONLY incremental events, typed and sequenced.
  - Event order protection: every event carries a bus-wide monotonic `sequence`;
    clients drop anything <= the last sequence they saw for that event type.
  - Dedup: `event_id` is unique per event.
  - Staleness: clients reject events whose occurred_at is older than a window
    (replay of ancient events must never overwrite fresher UI state).
  - Backpressure: per-connection bounded queue; slow clients drop events
    (never block the pipeline), and the server heartbeat closes dead clients.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from events.bus import BaseEvent

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_S = 20
CLIENT_IDLE_TIMEOUT_S = 60
QUEUE_MAX = 500

# Topics that carry a listing-level aggregate (entity filtering by listing id).
_LISTING_TOPICS = {
    "price.collected",
    "price.changed",
    "price.dropped",
    "price.spike",
    "stock.changed",
    "seller.changed",
    "promotion.started",
    "promotion.ended",
    "observation.quarantined",
    "listing.changed",
}
# Topics that carry a variant-level aggregate (entity filtering by variant id).
_VARIANT_TOPICS = {
    "prediction.generated",
    "prediction.updated",
    "decision.changed",
    "alert.triggered",
}


def aggregate_of(event: BaseEvent) -> tuple[str, str]:
    payload = event.payload or {}
    if event.event_type in _LISTING_TOPICS or payload.get("listing_id"):
        return "listing", str(payload.get("listing_id") or "")
    if event.event_type in _VARIANT_TOPICS or payload.get("product_variant_id"):
        return "product_variant", str(payload.get("product_variant_id") or "")
    return "system", ""


def build_envelope(event: BaseEvent) -> dict[str, Any]:
    """Typed, versioned wire envelope. Additive-only fields - never remove."""
    payload = event.payload or {}
    aggregate_type, aggregate_id = aggregate_of(event)
    occurred = event.occurred_at or datetime.now(timezone.utc)
    observed = payload.get("observed_at") or occurred.isoformat()
    return {
        "v": 1,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "sequence": event.sequence,
        "occurred_at": occurred.isoformat(),
        "observed_at": observed,
        "payload": payload,
    }


class RealtimeConnection:
    def __init__(self, ws: Any, topics: set[str], entities: set[str]) -> None:
        self.ws = ws
        self.topics = topics
        self.entities = entities
        self.connection_id = uuid.uuid4().hex[:12]
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_MAX)
        self.last_message_at = time.monotonic()
        self.dropped = 0

    def matches(self, event: BaseEvent) -> bool:
        if event.event_type not in self.topics:
            return False
        if not self.entities:
            return True
        _, aggregate_id = aggregate_of(event)
        return bool(aggregate_id) and aggregate_id in self.entities

    def deliver(self, envelope: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(envelope)
        except asyncio.QueueFull:
            self.dropped += 1
            logger.warning("realtime: slow client %s dropped %s events", self.connection_id, self.dropped)


class RealtimeHub:
    """Fanatical about one thing: fast, ordered, typed delivery to browsers."""

    def __init__(self, bus: Any) -> None:
        self._bus = bus
        self._connections: list[RealtimeConnection] = []
        self._heartbeat_task: asyncio.Task | None = None
        bus.subscribe(self._deliver)

    @property
    def connections(self) -> int:
        return len(self._connections)

    def _deliver(self, event: BaseEvent) -> None:
        envelope = build_envelope(event)
        for conn in list(self._connections):
            if conn.matches(event):
                conn.deliver(envelope)

    async def start_heartbeat(self) -> None:
        if self._heartbeat_task is not None:
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            now = time.monotonic()
            for conn in list(self._connections):
                try:
                    await conn.ws.send_json({"type": "ping", "sequence": None})
                    # also act as dead-connection detection: any client that
                    # stopped talking is closed by the reader loop; here we
                    # double-check the wire by attempting a send.
                except Exception:  # noqa: BLE001 - dead socket
                    logger.info("realtime: closing dead client %s", conn.connection_id)
                    try:
                        await conn.ws.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self._connections.remove(conn)

    async def handle(self, ws: Any, topics: set[str], entities: set[str]) -> None:
        conn = RealtimeConnection(ws, topics or set(), entities or set())
        self._connections.append(conn)
        await conn.ws.accept()
        await conn.ws.send_json(
            {
                "type": "hello",
                "connection_id": conn.connection_id,
                "topics": sorted(conn.topics),
                "entities": sorted(conn.entities),
                "server_time": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info("realtime: client %s connected (topics=%s)", conn.connection_id, sorted(conn.topics))
        try:
            while True:
                receive = asyncio.create_task(conn.ws.receive_text())
                outbound = asyncio.create_task(conn.queue.get())
                done, pending = await asyncio.wait(
                    {receive, outbound}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                if receive in done:
                    text = receive.result()
                    conn.last_message_at = time.monotonic()
                    await self._handle_client_message(conn, text)
                if outbound in done and not outbound.cancelled():
                    envelope = outbound.result()
                    await conn.ws.send_json(envelope)
                    if time.monotonic() - conn.last_message_at > CLIENT_IDLE_TIMEOUT_S:
                        raise ConnectionError("client idle")
        finally:
            self._connections.remove(conn)
            logger.info("realtime: client %s disconnected", conn.connection_id)

    async def _handle_client_message(self, conn: RealtimeConnection, text: str) -> None:
        import json

        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            return
        mtype = msg.get("type")
        if mtype == "ping":
            await conn.ws.send_json({"type": "pong", "sequence": None})
        elif mtype == "subscribe":
            conn.topics = set(msg.get("topics") or []) or conn.topics
            conn.entities = set(msg.get("entities") or []) or conn.entities
            await conn.ws.send_json({"type": "subscribed", "topics": sorted(conn.topics)})


_hub: RealtimeHub | None = None


def configure_hub(hub: RealtimeHub) -> None:
    global _hub
    _hub = hub


def get_hub() -> RealtimeHub:
    if _hub is None:
        raise RuntimeError("realtime hub not configured (lifespan did not run)")
    return _hub