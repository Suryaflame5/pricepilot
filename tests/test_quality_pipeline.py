"""V1.1 data quality pipeline tests: anomaly detection, quality scoring,
change detection, ingestion pipeline end-to-end (SQLite)."""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import numpy as np
import pytest
from sqlalchemy import select

from database.models import (
    Listing,
    MatchCandidate,
    PriceObservation,
    RawObservation,
    Retailer,
    SystemEvent,
)
from database.session import create_engine, create_session_factory, init_db
from events.bus import EventBus
from price_engine.anomaly import detect_anomaly
from price_engine.changes import detect_changes
from price_engine.collectors.base import CollectionResult
from price_engine.pipeline import IngestionPipeline
from price_engine.quality import QualityVerdict, score_observation, validate_state

DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_factory():
    engine = create_engine(DB_URL)
    await init_db(engine)
    yield create_session_factory(engine)
    await engine.dispose()


def _result(price=1000.0, mrp=1300.0, coupon=0.0, availability="IN_STOCK",
            retailer="croma", title="Sony WH-1000XM5 Headphones", identity=None):
    return CollectionResult(
        listing_id=str(uuid.uuid4()),
        price=price,
        mrp=mrp,
        shipping=0.0,
        coupon_discount=coupon,
        bank_discount=0.0,
        availability=availability,
        seller_name="TechZone",
        title=title,
        rating=4.5,
        review_count=1200,
        delivery_estimate="3-5 days",
        identity=identity or {"brand": "Sony", "model": "WH-1000XM5", "gtin": "4548736117576"},
        source_metadata={"name": "croma", "retailer": retailer, "mode": "page", "url": "http://x"},
    )


# ---------------------------------------------------------------- anomaly
class TestAnomaly:
    def test_normal_point_not_flagged(self):
        history = list(1000.0 + np.random.default_rng(1).normal(0, 8, 60))
        v = detect_anomaly(1005.0, history, previous=history[-1], retailer="croma")
        assert not v.is_anomaly

    def test_big_drop_flagged_by_retailer_threshold(self):
        history = list(1000.0 + np.random.default_rng(1).normal(0, 5, 60))
        v = detect_anomaly(620.0, history, previous=history[-1], retailer="croma")
        assert v.is_anomaly
        assert "retailer_threshold" in v.reasons

    def test_robust_zscore_isolated_outlier(self):
        history = list(1000.0 + np.random.default_rng(1).normal(0, 3, 30))
        v = detect_anomaly(1500.0, history, previous=history[-1], retailer="croma")
        assert v.is_anomaly
        assert "robust_z" in v.reasons

    def test_promotion_within_retailer_threshold_not_flagged(self):
        history = list(1000.0 + np.random.default_rng(2).normal(0, 20, 30))
        v = detect_anomaly(955.0, history, previous=history[-1], retailer="flipkart")
        assert not v.is_anomaly  # ~5% drop vs 2% daily noise = normal promo behavior


# ---------------------------------------------------------------- quality
class TestQuality:
    def test_valid_observation_trusted(self):
        state = {"price": 1000.0, "mrp": 1300.0, "availability": "IN_STOCK"}
        verdict = score_observation(state, source_mode="feed", match_confidence=0.99)
        assert verdict.tier == "TRUSTED"
        assert verdict.valid

    def test_missing_price_quarantined(self):
        state = {"price": None, "mrp": 1300.0, "availability": "IN_STOCK"}
        errors = validate_state(state)
        assert "price_missing" in errors
        verdict = score_observation(state, source_mode="feed", match_confidence=0.99)
        assert verdict.tier == "QUARANTINED"

    def test_price_above_mrp_bounds_flagged(self):
        state = {"price": 5000.0, "mrp": 1300.0, "availability": "IN_STOCK"}
        errors = validate_state(state)
        assert "price_exceeds_mrp" in errors

    def test_source_reliability_ordering(self):
        base = {"price": 1000.0, "mrp": 1300.0, "availability": "IN_STOCK"}
        feed = score_observation(base, source_mode="feed", match_confidence=0.99)
        page = score_observation(base, source_mode="page", match_confidence=0.99)
        assert feed.score > page.score


# ---------------------------------------------------------------- changes
class TestChanges:
    def _obs(self, price, coupon=0.0, availability="IN_STOCK", seller="A"):
        return {
            "price": price,
            "coupon_discount": coupon,
            "availability": availability,
            "seller_name": seller,
        }

    def test_price_dropped_event(self):
        events = detect_changes(self._obs(1000.0), self._obs(950.0))
        types = [e.event_type for e in events]
        assert "price.changed" in types and "price.dropped" in types

    def test_promotion_started_and_stock_events(self):
        events = detect_changes(
            self._obs(1000.0, coupon=0.0, availability="OUT_OF_STOCK"),
            self._obs(990.0, coupon=50.0, availability="IN_STOCK"),
        )
        types = [e.event_type for e in events]
        assert "promotion.started" in types and "stock.changed" in types

    def test_seller_change(self):
        events = detect_changes(self._obs(1000.0, seller="A"), self._obs(1000.0, seller="B"))
        assert [e.event_type for e in events] == ["seller.changed"]

    def test_no_events_when_unchanged(self):
        assert detect_changes(self._obs(1000.0), self._obs(1000.0)) == []


# ---------------------------------------------------------------- pipeline
class TestIngestionPipeline:
    async def test_first_observation_bootstraps_catalog(self, db_factory):
        bus = EventBus()
        collected = []
        bus.subscribe(lambda e: collected.append(e))
        pipeline = IngestionPipeline(db_factory, bus)

        reports = await pipeline.ingest_results([_result()], source_mode="page")
        report = reports[0]
        assert report["status"] == "VERIFIED"
        assert report["match_decision"] == "NO_MATCH"  # empty catalog -> new entry
        assert report["tier"] == "TRUSTED"

        async with db_factory() as db:
            raw = await db.get(RawObservation, report["raw_id"])
            assert raw.status == "VERIFIED"
            assert raw.quality_score is not None
            listing = await db.get(Listing, uuid.UUID(report["listing_id"]))
            assert listing.listing_title == "Sony WH-1000XM5 Headphones"
            obs = (await db.execute(select(PriceObservation))).scalars().all()
            assert len(obs) == 1
            assert obs[0].trust_tier == "TRUSTED"
            assert obs[0].source == "croma"
            assert obs[0].rating == 4.5
            events = (await db.execute(select(SystemEvent))).scalars().all()
            assert len(events) == 0  # first observation: no changes to detect

    async def test_second_observation_matches_and_emits_events(self, db_factory):
        pipeline = IngestionPipeline(db_factory, EventBus())
        r1 = (await pipeline.ingest_results([_result(price=1000.0)], source_mode="page"))[0]
        listing_id = uuid.UUID(r1["listing_id"])

        bus = EventBus()
        pipeline2 = IngestionPipeline(db_factory, bus)
        r2 = (await pipeline2.ingest_results(
            [_result(price=940.0, coupon=60.0)], source_mode="page", collected_at=datetime.now(timezone.utc) + timedelta(hours=6)
        ))[0]

        assert r2["match_decision"] == "AUTO_MATCH"
        assert r2["listing_id"] == r1["listing_id"]  # same product, same retailer
        assert "price.changed" in r2["events"]
        assert "price.dropped" in r2["events"]
        assert "promotion.started" in r2["events"]

        async with db_factory() as db:
            events = (await db.execute(select(SystemEvent))).scalars().all()
            types = {e.event_type for e in events}
            assert {"price.changed", "price.dropped", "promotion.started"} <= types

    async def test_review_match_creates_candidate_not_merge(self, db_factory):
        pipeline = IngestionPipeline(db_factory, EventBus())
        await pipeline.ingest_results([_result(title="Sony WH-1000XM5 Wireless Headphones")], source_mode="page")
        # near-identical title (one extra token) + same brand, no strong id match -> REVIEW band
        r2 = (await pipeline.ingest_results([
            _result(title="Sony WH-1000XM5 Wireless Headphones (Black)", identity={"brand": "Sony"})
        ], source_mode="page"))[0]
        assert r2["match_decision"] == "REVIEW"
        async with db_factory() as db:
            candidates = (await db.execute(select(MatchCandidate))).scalars().all()
            assert len(candidates) == 1
            assert candidates[0].status == "PENDING"
            # distinct listings: never merged below the auto bar
            listings = (await db.execute(select(Listing))).scalars().all()
            assert len(listings) == 2

    async def test_invalid_observation_quarantined(self, db_factory):
        pipeline = IngestionPipeline(db_factory, EventBus())
        bad = _result(price=None, mrp=1300.0)
        report = (await pipeline.ingest_results([bad], source_mode="page"))[0]
        assert report["status"] == "QUARANTINED"
        async with db_factory() as db:
            raw = await db.get(RawObservation, report["raw_id"])
            assert raw.status == "QUARANTINED"
            assert "price_missing" in raw.validation_errors
            obs = (await db.execute(select(PriceObservation))).scalars().all()
            assert len(obs) == 0  # nothing trusted

    async def test_anomaly_demotes_to_review(self, db_factory):
        pipeline = IngestionPipeline(db_factory, EventBus())
        rng = np.random.default_rng(3)
        listing_id = None
        price = 1000.0
        for i in range(40):
            r = (await pipeline.ingest_results(
                [_result(price=price, mrp=1300.0, title=f"Probe P{i}", identity={"brand": "Sony", "model": "X1", "sku": f"SKU-{i}"})],
                source_mode="page",
                collected_at=datetime.now(timezone.utc) + timedelta(hours=i),
            ))[0]
            if listing_id is None:
                listing_id = r["listing_id"]
            price *= 1 + rng.normal(0, 0.004)
        # 60% crash
        report = (await pipeline.ingest_results([
            _result(price=price * 0.5, mrp=1300.0, title="Probe P41", identity={"brand": "Sony", "model": "X1", "sku": "SKU-41"}),
        ], source_mode="page", collected_at=datetime.now(timezone.utc) + timedelta(hours=41)))[0]
        assert report["anomaly"]["is_anomaly"]
        assert report["tier"] == "REVIEW"
        async with db_factory() as db:
            obs = (await db.execute(select(PriceObservation))).scalars().all()
            assert obs[-1].trust_tier == "REVIEW"
            assert obs[-1].quality_score is not None
