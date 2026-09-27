"""Canonical Offer - the single language between collectors, comparison,
ML, the AI agent and checkout (V1.2).

An Offer is immutable and deterministic: every downstream consumer
(compare tools, planner, purchase workflow) reads the SAME shape and the
SAME effective_price formula. Agents never see raw prices/HTML - they see
precomputed offers.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class OfferSource(BaseModel):
    type: str  # page | feed | api | mock
    observed_at: datetime


class OfferTrust(BaseModel):
    tier: str  # TRUSTED | REVIEW | QUARANTINED
    score: float | None = None


class OfferDelivery(BaseModel):
    date: datetime | None = None
    days: int | None = None


class Offer(BaseModel):
    product_variant_id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID | None = None
    retailer_name: str
    seller_id: str | None = None
    seller_name: str | None = None

    listed_price: float | None = None
    shipping: float = 0.0
    coupon_discount: float = 0.0
    bank_discount: float = 0.0
    effective_price: float

    availability: str | None = None  # IN_STOCK / OUT_OF_STOCK / PRE_ORDER
    delivery: OfferDelivery | None = None

    source: OfferSource | None = None
    trust: OfferTrust | None = None

    currency: str = "INR"

    @property
    def expected_total(self) -> float:
        """Total the user pays. Deterministic: effective_price ALREADY includes
        shipping (pipeline: price + shipping - coupon - bank)."""
        return round(float(self.effective_price), 2)