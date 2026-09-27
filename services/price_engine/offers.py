"""Offer construction service (V1.2).

Builds canonical Offer objects from trusted, persisted observations. The
effective_price is always the observation's effective_price (computed once by
the collector) - never recomputed downstream, so comparison, ML, AI and
checkout all agree on the number.
"""

import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Listing, PriceObservation, ProductVariant, Retailer
from schemas.offer import Offer, OfferDelivery, OfferSource, OfferTrust

DEFAULT_TIER = "TRUSTED"
TIER_ORDER = {"TRUSTED": 0, "REVIEW": 1, "QUARANTINED": 2}


def offer_from_observation(
    listing: Listing,
    retailer: Retailer | None,
    obs: PriceObservation,
) -> Offer:
    """Immutably project one TRUSTED observation into an Offer."""
    effective = float(obs.effective_price) if obs.effective_price is not None else (
        float(obs.price or 0.0) + float(obs.shipping or 0.0)
        - float(obs.coupon_discount or 0.0) - float(obs.bank_discount or 0.0)
    )
    listing_price = float(obs.price) if obs.price is not None else None
    delivery = _parse_delivery(obs.delivery_estimate)
    return Offer(
        product_variant_id=listing.product_variant_id,
        listing_id=listing.id,
        retailer_id=retailer.id if retailer else None,
        retailer_name=retailer.name if retailer else listing.seller_name or "unknown",
        seller_id=_slug(listing.seller_name),
        seller_name=listing.seller_name,
        listed_price=listing_price,
        shipping=float(obs.shipping or 0.0),
        coupon_discount=float(obs.coupon_discount or 0.0),
        bank_discount=float(obs.bank_discount or 0.0),
        effective_price=round(max(0.0, effective), 2),
        availability=obs.availability,
        delivery=delivery,
        source=OfferSource(
            type=str(obs.source or "observation"),
            observed_at=obs.observed_at,
        ),
        trust=OfferTrust(
            tier=str(obs.trust_tier or DEFAULT_TIER),
            score=float(obs.quality_score) if obs.quality_score is not None else None,
        ),
    )


async def latest_offers(
    db: AsyncSession,
    variant_id: uuid.UUID,
    *,
    min_tier: str = DEFAULT_TIER,
    active_only: bool = True,
) -> list[Offer]:
    """Newest qualifying observation per active listing, cheapest first.

    Only observations at min_tier or better are returned - QUARANTINED data
    never reaches the agent or checkout.
    """
    stmt = select(Listing).where(Listing.product_variant_id == variant_id)
    if active_only:
        stmt = stmt.where(Listing.active.is_(True))
    listings = list(
        (await db.execute(stmt.options(selectinload(Listing.retailer)))).scalars().all()
    )
    offers: list[Offer] = []
    for listing in listings:
        obs = (
            await db.execute(
                select(PriceObservation)
                .where(PriceObservation.listing_id == listing.id)
                .order_by(PriceObservation.observed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if obs is None or obs.effective_price is None:
            continue
        tier = str(obs.trust_tier or DEFAULT_TIER)
        if TIER_ORDER.get(tier, 9) > TIER_ORDER.get(min_tier, 0):
            continue  # tier worse than the gate
        offers.append(offer_from_observation(listing, listing.retailer, obs))
    offers.sort(key=lambda o: (o.expected_total, o.retailer_name))
    return offers


async def cheapest_offer(
    db: AsyncSession,
    variant_id: uuid.UUID,
    *,
    min_tier: str = DEFAULT_TIER,
) -> Offer | None:
    offers = await latest_offers(db, variant_id, min_tier=min_tier)
    return offers[0] if offers else None


async def offer_by_listing(
    db: AsyncSession,
    listing_id: uuid.UUID,
    *,
    min_tier: str = DEFAULT_TIER,
) -> Offer | None:
    listing = (
        await db.execute(
            select(Listing)
            .where(Listing.id == listing_id)
            .options(selectinload(Listing.retailer))
        )
    ).scalar_one_or_none()
    if listing is None:
        return None
    obs = (
        await db.execute(
            select(PriceObservation)
            .where(PriceObservation.listing_id == listing_id)
            .order_by(PriceObservation.observed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if obs is None or obs.effective_price is None:
        return None
    tier = str(obs.trust_tier or DEFAULT_TIER)
    if TIER_ORDER.get(tier, 9) > TIER_ORDER.get(min_tier, 0):
        return None
    return offer_from_observation(listing, listing.retailer, obs)


def _parse_delivery(estimate: str | None) -> OfferDelivery | None:
    if not estimate:
        return None
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", estimate)
    if m:
        return OfferDelivery(days=int(m.group(1)))
    m = re.search(r"(\d+)\s*(?:business\s*)?days?", estimate, re.I)
    if m:
        return OfferDelivery(days=int(m.group(1)))
    return OfferDelivery(days=None)


def _slug(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or None