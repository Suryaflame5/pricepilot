"""V1.2 purchase workflow tests: ShoppingSession state machine, two
confirmations, price revalidation before purchase, provider isolation."""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import pytest

from database.models import Listing, PriceObservation, Product, ProductVariant, PurchaseOrder, Retailer
from database.session import create_engine, create_session_factory, init_db
from sqlalchemy import select
from purchase.base import PurchaseError
from purchase.registry import MockPurchaseProvider, get_provider, registered_providers
from purchase.session import (
    SESSION_EXPIRY_HOURS,
    TRANSITIONS,
    SessionStateError,
    confirm_offer,
    create_session,
    get_session,
    order_status,
    place_order,
    resolve_provider,
    select_offer,
    verify_price,
)

DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_factory():
    engine = create_engine(DB_URL)
    await init_db(engine)
    yield create_session_factory(engine)
    await engine.dispose()


async def _catalog(db, *, retailer_name="mock", price=1000.0, shipping=50.0, seller="TechZone"):
    retailer = Retailer(name=retailer_name, currency="INR")
    db.add(retailer)
    await db.flush()
    product = Product(canonical_name="Mock Phone X", brand="MockBrand", model="X", category="phones")
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, variant_name="X 128GB")
    db.add(variant)
    await db.flush()
    listing = Listing(
        product_variant_id=variant.id,
        retailer_id=retailer.id,
        seller_name=seller,
        listing_title="Mock Phone X 128GB",
    )
    db.add(listing)
    await db.flush()
    obs = PriceObservation(
        listing_id=listing.id,
        price=price,
        shipping=shipping,
        coupon_discount=0.0,
        bank_discount=0.0,
        effective_price=price + shipping,
        availability="IN_STOCK",
        observed_at=datetime.now(timezone.utc),
        trust_tier="TRUSTED",
        quality_score=0.95,
        delivery_estimate="3-5 business days",
        source="mock",
    )
    db.add(obs)
    await db.commit()
    return retailer, product, variant, listing


class TestStateMachine:
    def test_transitions_are_spec_locked(self):
        assert TRANSITIONS["SEARCHING"] == {"SELECTED"}
        assert TRANSITIONS["SELECTED"] == {"PRICE_VERIFIED"}
        assert TRANSITIONS["PRICE_VERIFIED"] == {"CHECKOUT_READY"}
        assert TRANSITIONS["CHECKOUT_READY"] == {"USER_CONFIRMED"}
        assert TRANSITIONS["USER_CONFIRMED"] == {"ORDER_PLACED"}
        assert TRANSITIONS["ORDER_PLACED"] == {"TRACKING"}
        assert TRANSITIONS["TRACKING"] == {"COMPLETED", "ORDER_PLACED"}

    async def test_full_flow_two_confirmations(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            s = await create_session(db, product_variant_id=variant.id, strategy="IMMEDIATE")
            assert s.status == "SEARCHING"
            assert s.expires_at > datetime.now(timezone.utc)

            # confirmation 1: choose offer
            await select_offer(db, s, listing.id)
            assert s.status == "SELECTED"
            assert s.selected_offer["effective_price"] == 1050.0

            verified = await verify_price(db, s)
            assert s.status == "PRICE_VERIFIED"
            assert verified["price_changed"] is False

            ready = await confirm_offer(db, s, MockPurchaseProvider())
            assert s.status == "CHECKOUT_READY"
            assert ready["checkout_total"] == 1050.0
            assert ready["delivery_estimate"] == "3 business days"

            # confirmation 2: final total -> execute
            placed = await place_order(db, s, MockPurchaseProvider())
            assert s.status == "ORDER_PLACED"
            assert placed["order_ref"] == "MOCK-000001"

            order = (
                await db.execute(
                    select(PurchaseOrder).where(PurchaseOrder.session_id == s.id)
                )
            ).scalar_one()
            assert order.total == 1050.0
            assert order.provider == "mock"

            status = await order_status(db, s, MockPurchaseProvider())
            assert s.status == "TRACKING"
            assert status["status"] == "TRACKING"

    async def test_confirm_without_verify_blocked(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            s = await create_session(db, product_variant_id=variant.id)
            await select_offer(db, s, listing.id)
            with pytest.raises(SessionStateError):
                await confirm_offer(db, s, MockPurchaseProvider())

    async def test_place_order_requires_confirm(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            s = await create_session(db, product_variant_id=variant.id)
            await select_offer(db, s, listing.id)
            await verify_price(db, s)
            with pytest.raises(SessionStateError):
                await place_order(db, s, MockPurchaseProvider())

    async def test_price_drift_blocks_purchase(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            s = await create_session(db, product_variant_id=variant.id)
            await select_offer(db, s, listing.id)
            await verify_price(db, s)
            await confirm_offer(db, s, MockPurchaseProvider())
            assert s.status == "CHECKOUT_READY"

            # price moves before the user confirms purchase #2
            db.add(PriceObservation(
                listing_id=listing.id, price=1100.0, shipping=50.0,
                effective_price=1150.0, availability="IN_STOCK",
                observed_at=datetime.now(timezone.utc),
                trust_tier="TRUSTED", source="mock",
            ))
            await db.commit()

            with pytest.raises(SessionStateError) as exc:
                await place_order(db, s, MockPurchaseProvider(), accept=True)
            assert "price changed" in str(exc.value)
            assert s.status in ("CHECKOUT_READY", "PRICE_VERIFIED", "USER_CONFIRMED")  # never ORDER_PLACED

    async def test_expiry(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            s = await create_session(
                db, product_variant_id=variant.id,
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            await db.commit()
            with pytest.raises(SessionStateError) as exc:
                await get_session(db, s.id)
            assert "expired" in str(exc.value)

    async def test_explicit_not_accept_blocks(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            s = await create_session(db, product_variant_id=variant.id)
            await select_offer(db, s, listing.id)
            await verify_price(db, s)
            with pytest.raises(SessionStateError):
                await confirm_offer(db, s, MockPurchaseProvider(), accept=False)


class TestProviderIsolation:
    async def test_unregistered_retailer_has_no_provider(self, db_factory):
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db, retailer_name="croma")
            s = await create_session(db, product_variant_id=variant.id)
            await select_offer(db, s, listing.id)
            with pytest.raises(PurchaseError) as exc:
                resolve_provider(s)
            assert "only retailer-permitted integrations" in str(exc.value)

    async def test_registered_provider_only(self):
        assert registered_providers() == ["mock"]
        assert isinstance(get_provider("mock"), MockPurchaseProvider)
        with pytest.raises(PurchaseError):
            get_provider("amazon")

    async def test_quarantine_observation_blocks_selection(self, db_factory):
        """A newer QUARANTINED observation must never become the 'price'."""
        async with db_factory() as db:
            _, _, variant, listing = await _catalog(db)
            db.add(PriceObservation(
                listing_id=listing.id, price=100.0, effective_price=100.0,
                availability="IN_STOCK", observed_at=datetime.now(timezone.utc) + timedelta(days=1),
                trust_tier="QUARANTINED", source="mock",
            ))
            await db.commit()
            from price_engine.offers import offer_by_listing

            assert await offer_by_listing(db, listing.id) is None  # quarantine never surfaces
            s = await create_session(db, product_variant_id=variant.id)
            with pytest.raises(SessionStateError):
                await select_offer(db, s, listing.id)