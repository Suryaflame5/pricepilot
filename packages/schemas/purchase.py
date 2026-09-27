"""Purchase workflow schemas (V1.2 P1)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.offer import Offer

SESSION_STATUSES = (
    "SEARCHING",
    "SELECTED",
    "PRICE_VERIFIED",
    "CHECKOUT_READY",
    "USER_CONFIRMED",
    "ORDER_PLACED",
    "TRACKING",
    "COMPLETED",
)


class ShoppingSessionCreate(BaseModel):
    product_variant_id: uuid.UUID
    strategy: str = "IMMEDIATE"
    conversation_id: str | None = Field(default=None, max_length=64)
    user_id: uuid.UUID | None = None


class SelectListingIn(BaseModel):
    listing_id: uuid.UUID


class ConfirmIn(BaseModel):
    accept: bool = True


class SessionOut(BaseModel):
    id: uuid.UUID
    product_variant_id: uuid.UUID
    conversation_id: str | None
    strategy: str
    status: str
    selected_listing_id: uuid.UUID | None = None
    selected_offer: dict = {}
    checkout_total: float | None = None
    delivery_estimate: str | None = None
    created_at: datetime
    expires_at: datetime


class SessionWithOffersOut(SessionOut):
    offers: list[dict] = []


class PriceVerificationOut(BaseModel):
    status: str
    price_changed: bool = False
    previous_effective_price: float | None = None
    current_effective_price: float | None = None
    checkout_total: float | None = None


class CheckoutReadyOut(BaseModel):
    status: str
    checkout_total: float | None = None
    delivery_estimate: str | None = None
    offer: dict = {}


class OrderPlacedOut(BaseModel):
    status: str
    order_ref: str | None = None
    provider: str | None = None
    retailer_name: str | None = None
    total: float | None = None
    tracking_url: str | None = None


class OrderStatusOut(BaseModel):
    status: str
    order_ref: str | None = None
    provider: str | None = None
    retailer_name: str | None = None
    detail: str | None = None
    tracking_url: str | None = None