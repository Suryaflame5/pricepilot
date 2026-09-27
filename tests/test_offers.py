"""V1.2 offer builder tests: canonical Offer semantics, tier gating, delivery."""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import pytest

from database.models import Listing, PriceObservation, Product, ProductVariant, Retailer
from database.session import create_engine, create_session_factory, init_db
from price_engine.offers import (
    cheapest_offer,
    latest_offers,
    offer_by_listing,
    offer_from_observation,
    _parse_delivery,
    _slug,
)
from schemas.offer import Offer

DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_factory():
    engine = create_engine(DB_URL)
    await init_db(engine)
    yield create_session_factory(engine)
    await engine.dispose()


def _listing(retailer_name: str = "croma") -> Listing:
    return Listing(id=uuid.uuid4(), product_variant_id=uuid.uuid4(), retailer_id=uuid.uuid4())


def _retailer(name: str = "croma") -> Retailer:
    return Retailer(id=uuid.uuid4(), name=name)


def _obs(
    *,
    price=1000.0,
    shipping=50.0,
    coupon=100.0,
    bank=0.0,
    trust="TRUSTED",
    quality=0.9,
    availability="IN_STOCK",
    delivery="3-5 business days",
    source="croma",
    observed_at=None,
) -> PriceObservation:
    return PriceObservation(
        price=price,
        shipping=shipping,
        coupon_discount=coupon,
        bank_discount=bank,
        effective_price=max(0.0, price + shipping - coupon - bank),
        availability=availability,
        trust_tier=trust,
        quality_score=quality,
        delivery_estimate=delivery,
        source=source,
        observed_at=observed_at or datetime.now(timezone.utc),
    )


class TestOfferProjection:
    def test_effective_price_identical_to_observation(self):
        obs = _obs(price=1000.0, shipping=50.0, coupon=200.0)
        offer = offer_from_observation(_listing(), _retailer(), obs)
        assert isinstance(offer, Offer)
        assert offer.effective_price == 850.0  # shipping already inside effective
        assert offer.expected_total == 850.0

    def test_components_and_provenance(self):
        listing = _listing()
        obs = _obs()
        offer = offer_from_observation(listing, _retailer("croma"), obs)
        assert offer.listed_price == 1000.0
        assert offer.retailer_name == "croma"
        assert offer.trust.tier == "TRUSTED"
        assert offer.trust.score == 0.9
        assert offer.source.type == "croma"
        assert offer.seller_name is None  # listing had none
        assert offer.seller_id is None

    def test_delivery_parse(self):
        assert _parse_delivery("3-5 business days").days == 3
        assert _parse_delivery("7 days").days == 7
        assert _parse_delivery(None) is None

    def test_slug(self):
        assert _slug("Tech Zone India Pvt") == "tech-zone-india-pvt"
        assert _slug("  ") is None
        assert _slug(None) is None

    def test_immutability_shape(self):
        offer = offer_from_observation(_listing(), _retailer(), _obs())
        dumped = offer.model_dump(mode="json")
        assert set(dumped) == {
            "product_variant_id", "listing_id", "retailer_id", "retailer_name",
            "seller_id", "seller_name", "listed_price", "shipping", "coupon_discount",
            "bank_discount", "effective_price", "availability", "delivery", "source",
            "trust", "currency",
        }


class TestTierGate:
    @staticmethod
    async def _catalog(db, *, tiers: list[str], prices: list[float]):
        retailer = Retailer(name="croma", currency="INR")
        db.add(retailer)
        await db.flush()
        product = Product(canonical_name="Sony WH-1000XM5", brand="Sony", model="WH-1000XM5")
        db.add(product)
        await db.flush()
        variant = ProductVariant(product_id=product.id, variant_name="Black")
        db.add(variant)
        await db.flush()
        listings = []
        for i, (tier, price) in enumerate(zip(tiers, prices)):
            listing = Listing(
                product_variant_id=variant.id,
                retailer_id=retailer.id,
                seller_name=f"Seller {i}",
                listing_title="Sony WH-1000XM5",
            )
            db.add(listing)
            await db.flush()
            obs = _obs(
                price=price,
                shipping=0.0,
                coupon=0.0,
                trust=tier,
                observed_at=datetime.now(timezone.utc),
            )
            obs.listing_id = listing.id
            db.add(obs)
            listings.append(listing)
        await db.commit()
        return variant.id

    async def test_quarantine_never_surfaces(self, db_factory):
        async with db_factory() as db:
            variant_id = await TestTierGate._catalog(
                db, tiers=["TRUSTED", "QUARANTINED"], prices=[1000.0, 500.0]
            )
            offers = await latest_offers(db, variant_id)
            assert len(offers) == 1
            assert offers[0].effective_price == 1000.0

    async def test_review_excluded_by_default(self, db_factory):
        async with db_factory() as db:
            variant_id = await TestTierGate._catalog(
                db, tiers=["TRUSTED", "REVIEW"], prices=[1000.0, 900.0]
            )
            assert len(await latest_offers(db, variant_id)) == 1

    async def test_review_included_when_gate_relaxed(self, db_factory):
        async with db_factory() as db:
            variant_id = await TestTierGate._catalog(
                db, tiers=["TRUSTED", "REVIEW"], prices=[1000.0, 900.0]
            )
            offers = await latest_offers(db, variant_id, min_tier="REVIEW")
            assert len(offers) == 2

    async def test_cheapest_sorting_and_expected_total(self, db_factory):
        async with db_factory() as db:
            variant_id = await TestTierGate._catalog(
                db, tiers=["TRUSTED", "TRUSTED"], prices=[1000.0, 950.0]
            )
            cheapest = await cheapest_offer(db, variant_id)
            assert cheapest.effective_price == 950.0
            assert cheapest.seller_name == "Seller 1"

    async def test_offer_by_listing(self, db_factory):
        async with db_factory() as db:
            variant_id = await TestTierGate._catalog(
                db, tiers=["TRUSTED", "TRUSTED"], prices=[1000.0, 950.0]
            )
            from sqlalchemy import select

            listing = (await db.execute(select(Listing))).scalars().first()
            offer = await offer_by_listing(db, listing.id)
            assert offer is not None
            assert offer.listing_id == listing.id