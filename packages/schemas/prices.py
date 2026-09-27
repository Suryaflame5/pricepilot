"""Price observation / history / statistics API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PriceObservationIn(BaseModel):
    listing_id: uuid.UUID
    price: float
    mrp: float | None = None
    shipping: float = 0
    coupon_discount: float = 0
    bank_discount: float = 0
    availability: str | None = "IN_STOCK"
    observed_at: datetime | None = None


class RawObservationIn(BaseModel):
    """Full state as collected - the V1.1 quarantine-first intake path."""

    source: str = "http"
    source_mode: str = "page"  # feed | page | mock
    retailer: str
    collected_at: datetime | None = None
    listing_id: uuid.UUID | None = None
    url: str | None = None
    title: str | None = None
    seller_name: str | None = None
    price: float | None = None
    mrp: float | None = None
    shipping: float = 0
    coupon_discount: float = 0
    bank_discount: float = 0
    availability: str = "IN_STOCK"
    rating: float | None = None
    review_count: int | None = None
    delivery_estimate: str | None = None
    identity: dict = {}


class RawObservationOut(BaseModel):
    raw_id: int | None = None
    listing_id: str | None = None
    status: str
    quality: dict | None = None
    anomaly: dict | None = None
    tier: str | None = None
    match_decision: str | None = None
    match_score: float | None = None
    events: list[str] = []
    reasons: dict | None = None
    effective_price: float | None = None


class PriceObservationOut(BaseModel):
    listing_id: uuid.UUID
    retailer_name: str | None = None
    price: float | None
    mrp: float | None
    shipping: float | None
    coupon_discount: float | None
    bank_discount: float | None
    effective_price: float | None
    availability: str | None
    observed_at: datetime


class PricePoint(BaseModel):
    t: datetime
    price: float
    effective_price: float | None = None


class PriceHistoryOut(BaseModel):
    listing_id: uuid.UUID
    variant_id: uuid.UUID
    points: list[PricePoint]


class PriceStatsOut(BaseModel):
    listing_id: uuid.UUID
    current_price: float | None
    mean_7d: float | None
    mean_30d: float | None
    mean_90d: float | None
    min_7d: float | None
    min_30d: float | None
    min_90d: float | None
    max_7d: float | None
    max_30d: float | None
    max_90d: float | None
    price_percentile_90d: float | None
    observations_90d: int


class RetailerPriceOut(BaseModel):
    listing_id: uuid.UUID
    retailer_name: str
    current_price: float
    effective_price: float
    url: str | None = None
    availability: str | None
    observed_at: datetime | None


class CompareOut(BaseModel):
    variant_id: uuid.UUID
    product_name: str
    cheapest: RetailerPriceOut | None = None
    offers: list[RetailerPriceOut]


ResampleInterval = Literal["1h", "6h", "1d", "1w"]
