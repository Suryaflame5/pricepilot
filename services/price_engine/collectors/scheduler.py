"""Adaptive polling scheduler (V1.2 P0 - continuous price intelligence).

Every active listing gets its OWN poll interval computed from measured
behavior: high volatility / active alerts / frequent price changes are polled
often; slow movers are polled rarely; inactive listings back off to weekly.

    next_interval = scheduler.predict_next_interval(
        volatility, alert_count, price_change_rate, retailer)

The interval per listing is persisted (listings.poll_interval_seconds,
last_collected_at) so rounds are resumable across restarts.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import Listing, PriceAlert, PriceObservation, Retailer
from price_engine.collectors.base import Collector, run_targets

logger = logging.getLogger(__name__)

POLL_MIN_SECONDS = 30 * 60  # floor: every 30 minutes (flash-sale retailers)
POLL_MAX_SECONDS = 7 * 24 * 3600  # ceiling: weekly
DEFAULT_INTERVAL_SECONDS = 4 * 3600

CHANGE_EPSILON_RATIO = 0.005  # a price move counts if |Δ| > 0.5% of price

# Per-retailer pace multipliers (flash-sale oriented retailers poll faster).
RETAILER_PACE = {
    "amazon": 1.0,
    "flipkart": 0.8,
    "croma": 1.2,
    "reliance_digital": 1.2,
    "mock": 1.0,
}

# Behavior -> pace multiplier. The FIRST matching row wins: stable/slow items
# are polled more rarely, volatile/alerted/churning items more often.
VOL_LEVELS = [(0.01, 2.0), (0.03, 1.0), (0.08, 0.5), (float("inf"), 0.3)]
ALERT_LEVELS = [(0, 1.0), (1, 0.5), (3, 0.33)]
CHANGE_LEVELS = [(0.05, 1.2), (0.25, 1.0), (float("inf"), 0.6)]


def _multiplier(levels, value: float) -> float:
    for level, m in levels:
        if value <= level:
            return m
    return levels[-1][1]


def predict_next_interval(
    volatility: float,
    alert_count: int,
    price_change_rate: float,
    retailer: str | None = None,
    base_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> int:
    """Deterministic interval selection from behavior signals.

    volatility: coefficient of variation of recent effective prices.
    alert_count: active user price-alerts on the listing's variant.
    price_change_rate: fraction of consecutive observations that moved.
    """
    vol = max(0.0, float(volatility) if volatility is not None and volatility == volatility else 0.0)
    rate = max(0.0, float(price_change_rate) if price_change_rate == price_change_rate else 0.0)
    alerts = max(0, int(alert_count))

    mult = (
        _multiplier(VOL_LEVELS, vol)
        * _multiplier(ALERT_LEVELS, alerts)
        * _multiplier(CHANGE_LEVELS, rate)
    )
    mult *= RETAILER_PACE.get((retailer or "").strip().lower(), 1.0)
    interval = int(base_seconds * mult)
    return int(max(POLL_MIN_SECONDS, min(POLL_MAX_SECONDS, interval)))


def interval_tier(seconds: int) -> str:
    if seconds <= 2 * 3600:
        return "FAST"
    if seconds <= 12 * 3600:
        return "NORMAL"
    if seconds <= 48 * 3600:
        return "SLOW"
    return "INACTIVE"


def volatility_of(prices: list[float]) -> float:
    """Coefficient of variation of the last <=30 observations."""
    if len(prices) < 2:
        return 0.0
    arr = np.asarray(prices[-30:], dtype=float)
    mean = float(arr.mean())
    if mean <= 0:
        return 0.0
    return float(arr.std(ddof=1) / mean)


def price_change_rate_of(prices: list[float]) -> float:
    """Fraction of consecutive pairs whose |Δ| > 0.5% of the earlier price."""
    if len(prices) < 2:
        return 0.0
    moves = 0
    for prev, cur in zip(prices[:-1], prices[1:]):
        if prev and abs(cur - prev) / abs(prev) > CHANGE_EPSILON_RATIO:
            moves += 1
    return moves / (len(prices) - 1)


@dataclass
class SchedulerTarget:
    listing_id: uuid.UUID
    url: str | None
    interval_seconds: int
    tier: str
    volatility: float
    alert_count: int
    price_change_rate: float
    due: bool


class AdaptiveScheduler:
    """Computes per-listing intervals from DB truth and runs due collections."""

    def __init__(self, db_factory: async_sessionmaker) -> None:
        self._db_factory = db_factory

    async def compute_targets(self, db: AsyncSession, now: datetime | None = None) -> list[SchedulerTarget]:
        now = now or datetime.now(timezone.utc)
        stmt = (
            select(Listing, Retailer)
            .outerjoin(Retailer, Listing.retailer_id == Retailer.id)
            .where(Listing.active.is_(True))
        )
        rows = (await db.execute(stmt)).all()
        targets: list[SchedulerTarget] = []
        for listing, retailer in rows:
            prices = await self._recent_prices(db, listing.id)
            alert_count = await self._alert_count(db, listing.product_variant_id)
            vol = volatility_of(prices)
            rate = price_change_rate_of(prices)
            interval = predict_next_interval(
                vol, alert_count, rate,
                retailer=retailer.name if retailer else None,
            )
            last = listing.last_collected_at
            due = last is None or (last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last) + timedelta(
                seconds=interval
            ) <= now
            targets.append(
                SchedulerTarget(
                    listing_id=listing.id,
                    url=listing.url,
                    interval_seconds=interval,
                    tier=interval_tier(interval),
                    volatility=round(vol, 4),
                    alert_count=alert_count,
                    price_change_rate=round(rate, 4),
                    due=due,
                )
            )
        return targets

    async def _recent_prices(self, db: AsyncSession, listing_id: uuid.UUID) -> list[float]:
        stmt = (
            select(PriceObservation.effective_price)
            .where(
                PriceObservation.listing_id == listing_id,
                PriceObservation.effective_price.isnot(None),
            )
            .order_by(PriceObservation.observed_at.desc())
            .limit(30)
        )
        return [float(v) for (v,) in (await db.execute(stmt)).all()]

    async def _alert_count(self, db: AsyncSession, variant_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(PriceAlert).where(
            PriceAlert.product_variant_id == variant_id, PriceAlert.active.is_(True)
        )
        return int((await db.execute(stmt)).scalar_one())

    @staticmethod
    async def persist_interval(
        db: AsyncSession,
        listing_id: uuid.UUID,
        interval_seconds: int,
        collected_at: datetime | None = None,
    ) -> None:
        """Write the computed interval + collection timestamp back to the listing."""
        listing = await db.get(Listing, listing_id)
        if listing is None:
            return
        listing.poll_interval_seconds = interval_seconds
        if collected_at is not None:
            listing.last_collected_at = collected_at

    async def run_round(
        self,
        db: AsyncSession,
        collector: Collector,
        on_results=None,
        now: datetime | None = None,
        dry_run: bool = False,
    ) -> dict:
        """Collect every due target, persist new intervals, return a report.

        All persistence happens in this one transaction; on_results (e.g. the
        IngestionPipeline sink) runs after commit.
        """
        now = now or datetime.now(timezone.utc)
        targets = await self.compute_targets(db, now=now)
        due = [t for t in targets if t.due]
        report = {
            "targets": len(targets),
            "due": len(due),
            "collected": 0,
            "failed": [],
            "tiers": {"FAST": 0, "NORMAL": 0, "SLOW": 0, "INACTIVE": 0},
        }
        for t in targets:
            report["tiers"][t.tier] += 1

        results: list = []
        failed: list[str] = []
        if due and not dry_run:
            async def _on_error(listing_id: str, exc: Exception) -> None:
                failed.append(str(listing_id))
                logger.warning("collect %s failed: %s", listing_id, exc)

            results = await run_targets(collector, [(str(t.listing_id), t.url) for t in due], on_error=_on_error)

        for t in targets:
            await self.persist_interval(db, t.listing_id, t.interval_seconds, collected_at=now)
        await db.commit()

        report["collected"] = len(results)
        report["failed"] = failed
        if results and on_results is not None:
            cb = on_results(results)
            if hasattr(cb, "__await__"):
                await cb
        return report

    async def run_forever(
        self,
        collector: Collector,
        on_results=None,
        poll_ms: int = 60_000,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Background loop: normal distributed polling implies a service, but
        this keeps the same AdaptiveScheduler logic usable in-process."""
        stop = stop_event or asyncio.Event()
        while not stop.is_set():
            try:
                async with self._db_factory() as db:
                    report = await self.run_round(db, collector, on_results=on_results)
                    logger.info("polling round: %s", report)
            except Exception:  # noqa: BLE001 - loop must survive transient failures
                logger.exception("polling round failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_ms / 1000)
            except TimeoutError:
                pass