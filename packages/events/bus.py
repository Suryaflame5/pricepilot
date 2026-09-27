"""Event schemas + bus. Persistent log via SystemEvent table, streaming via Redis Streams
(or in-memory fallback). The persisted log is the replay/monitoring source of truth;
the stream is for low-latency consumers (alerts, dashboard, shadow runner)."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

EventType = Literal[
    "price.collected",
    "price.validated",
    "price.changed",
    "price.dropped",
    "price.spike",
    "stock.changed",
    "seller.changed",
    "promotion.started",
    "promotion.ended",
    "observation.quarantined",
    "match.candidate.created",
    "listing.changed",
    "prediction.generated",
    "prediction.updated",
    "calibration.drift",
    "model.promoted",
    "alert.triggered",
    "decision.changed",
]

# Thresholds for change-event generation (shared so consumers see one policy)
CHANGE_EVENT_THRESHOLDS = {
    "drop_pct": 0.02,     # price.dropped at >= 2% below previous
    "spike_pct": 0.05,    # price.spike at >= 5% above previous within a short window
}


class BaseEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str = ""
    event_type: str
    occurred_at: datetime = None  # type: ignore[assignment]
    sequence: int | None = None
    payload: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if self.occurred_at is None:
            self.occurred_at = datetime.now(timezone.utc)


class PriceCollectedEvent(BaseEvent):
    event_type: str = "price.collected"
    payload: dict[str, Any] = {}


class PriceChangedEvent(BaseEvent):
    event_type: str = "price.changed"
    payload: dict[str, Any] = {}


class AlertTriggeredEvent(BaseEvent):
    event_type: str = "alert.triggered"
    payload: dict[str, Any] = {}


class CalibrationDriftEvent(BaseEvent):
    event_type: str = "calibration.drift"
    payload: dict[str, Any] = {}


class ModelPromotedEvent(BaseEvent):
    event_type: str = "model.promoted"
    payload: dict[str, Any] = {}


class EventBus:
    """Pub/sub wrapper. Redis Streams in production, in-memory fallback for tests/dev.

    Every published event is ALSO meant to be persisted to system_events by the caller
    (or by a subscribe-and-persist consumer); the bus itself stays fast and best-effort.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis = None
        self._memory_subscribers: list[Any] = []
        self._seq = 0

    def subscribe(self, callback: Any) -> None:
        """In-memory subscriber for tests and single-process dev."""
        self._memory_subscribers.append(callback)

    async def publish(self, event: BaseEvent) -> None:
        # Monotonic sequence: consumers reject anything older than the last
        # event they saw for the same type (WS replay protection).
        if event.sequence is None:
            event.sequence = self._seq
            self._seq += 1
        for cb in list(self._memory_subscribers):
            try:
                result = cb(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass
        if self._redis_url:
            try:
                import redis.asyncio as aioredis

                if self._redis is None:
                    self._redis = aioredis.from_url(self._redis_url)
                await self._redis.xadd(
                    f"events:{event.event_type}", event.model_dump(mode="json")
                )
            except Exception:
                pass  # never let the bus break the core pipeline


def serialize_event(event: BaseEvent) -> str:
    return json.dumps(event.model_dump())
