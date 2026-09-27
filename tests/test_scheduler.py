"""V1.2 adaptive polling tests: interval policy, tiers, round persistence."""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import pytest

from database.models import Listing, Product, ProductVariant, Retailer
from database.session import create_engine, create_session_factory, init_db
from ml.datasets.seed_db import seed
from price_engine.collectors.mock import MockCollector
from price_engine.collectors.scheduler import (
    DEFAULT_INTERVAL_SECONDS,
    POLL_MAX_SECONDS,
    POLL_MIN_SECONDS,
    AdaptiveScheduler,
    interval_tier,
    predict_next_interval,
    price_change_rate_of,
    volatility_of,
)

DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_factory():
    engine = create_engine(DB_URL)
    await init_db(engine)
    yield create_session_factory(engine)
    await engine.dispose()


class TestIntervalPolicy:
    def test_floor_and_ceiling_respected(self):
        assert predict_next_interval(0.0, 0, 0.0, base_seconds=30) == POLL_MIN_SECONDS
        assert predict_next_interval(0.0, 0, 0.0, base_seconds=10 ** 9) == POLL_MAX_SECONDS

    def test_volatility_shortens(self):
        low = predict_next_interval(0.005, 0, 0.0)
        high = predict_next_interval(0.10, 0, 0.0)
        assert high < low

    def test_alerts_shorten(self):
        no_alerts = predict_next_interval(0.02, 0, 0.05)
        alerts = predict_next_interval(0.02, 4, 0.05)
        assert alerts < no_alerts

    def test_change_rate_shortens(self):
        slow = predict_next_interval(0.02, 0, 0.02)
        fast = predict_next_interval(0.02, 0, 0.50)
        assert fast < slow

    def test_default_interval_for_calm_listing(self):
        # calm & unreferenced -> poll slower than base (stable = rare changes)
        assert predict_next_interval(0.0, 0, 0.0) > DEFAULT_INTERVAL_SECONDS

    def test_retailer_multiplier(self):
        amazon = predict_next_interval(0.02, 0, 0.05, retailer="amazon")
        flipkart = predict_next_interval(0.02, 0, 0.05, retailer="flipkart")
        croma = predict_next_interval(0.02, 0, 0.05, retailer="croma")
        assert flipkart < amazon < croma

    def test_deterministic(self):
        a = predict_next_interval(0.03, 2, 0.12, retailer="amazon")
        b = predict_next_interval(0.03, 2, 0.12, retailer="amazon")
        assert a == b

    def test_tier_labels(self):
        assert interval_tier(1800) == "FAST"
        assert interval_tier(6 * 3600) == "NORMAL"
        assert interval_tier(30 * 3600) == "SLOW"
        assert interval_tier(POLL_MAX_SECONDS) == "INACTIVE"


class TestMetricHelpers:
    def test_volatility_of_flat_series_is_zero(self):
        assert volatility_of([100.0] * 10) == 0.0

    def test_volatility_of_oscillating_series(self):
        prices = [100.0, 110.0, 90.0, 108.0, 92.0] * 4
        assert volatility_of(prices) > 0.01

    def test_change_rate(self):
        assert price_change_rate_of([100.0] * 5) == 0.0
        assert price_change_rate_of([100.0, 105.0, 110.0]) > 0.5


class TestAdaptiveSchedulerRounds:
    async def test_compute_targets_and_due(self, db_factory):
        async with db_factory() as db:
            async with db_factory() as seed_db:
                await seed(seed_db, products=1, days=90, obs_per_day=2)
            scheduler = AdaptiveScheduler(db_factory)
            targets = await scheduler.compute_targets(db)
            assert len(targets) == 3  # one active listing per seeded retailer
            for t in targets:
                assert POLL_MIN_SECONDS <= t.interval_seconds <= POLL_MAX_SECONDS
                assert t.due is True  # never collected -> due

    async def test_run_round_persists_interval_and_collects(self, db_factory):
        async with db_factory() as db:
            async with db_factory() as seed_db:
                await seed(seed_db, products=1, days=90, obs_per_day=2)
            listing_id = None
            async with db_factory() as read_db:
                from sqlalchemy import select

                listing_id = (await read_db.execute(select(Listing))).scalars().first().id

            scheduler = AdaptiveScheduler(db_factory)
            report = await scheduler.run_round(
                db, MockCollector(base_price=1000.0),
                on_results=None,
                now=datetime.now(timezone.utc),
            )
            assert report["targets"] == 3
            assert report["due"] == 3
            assert report["collected"] == 3

            async with db_factory() as read_db:
                from sqlalchemy import select

                listing = (
                    await read_db.execute(select(Listing).where(Listing.id == listing_id))
                ).scalar_one()
                assert listing.poll_interval_seconds is not None
                assert listing.last_collected_at is not None

    async def test_dry_run_collects_nothing(self, db_factory):
        async with db_factory() as db:
            async with db_factory() as seed_db:
                await seed(seed_db, products=1, days=30, obs_per_day=1)
            scheduler = AdaptiveScheduler(db_factory)
            report = await scheduler.run_round(db, MockCollector(), dry_run=True)
            assert report["due"] == 3
            assert report["collected"] == 0

    async def test_recently_collected_not_due(self, db_factory):
        async with db_factory() as db:
            async with db_factory() as seed_db:
                await seed(seed_db, products=1, days=30, obs_per_day=1)
            from sqlalchemy import select

            listing = (await db.execute(select(Listing))).scalars().first()
            listing.last_collected_at = datetime.now(timezone.utc)
            await db.commit()
            scheduler = AdaptiveScheduler(db_factory)
            targets = await scheduler.compute_targets(db, now=datetime.now(timezone.utc))
            assert targets[0].due is False