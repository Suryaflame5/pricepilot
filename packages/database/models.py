"""PricePilot database models (blueprint sections 3/4)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON as JSONType,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    watchlist: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["PriceAlert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    brand: Mapped[str | None] = mapped_column(String(255), index=True)
    model: Mapped[str | None] = mapped_column(String(255), index=True)
    canonical_name: Mapped[str] = mapped_column(String(500), index=True)
    category: Mapped[str | None] = mapped_column(String(255), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    variant_name: Mapped[str | None] = mapped_column(String(500))
    color: Mapped[str | None] = mapped_column(String(255))
    storage: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[str | None] = mapped_column(String(255))
    condition: Mapped[str | None] = mapped_column(String(255))
    gtin: Mapped[str | None] = mapped_column(String(64), index=True)
    sku: Mapped[str | None] = mapped_column(String(255), index=True)

    product: Mapped[Product] = relationship(back_populates="variants")
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )


class Retailer(Base):
    __tablename__ = "retailers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(8))
    currency: Mapped[str | None] = mapped_column(String(8), default="INR")

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="retailer", cascade="all, delete-orphan"
    )


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_variant_retailer", "product_variant_id", "retailer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), index=True
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id"))
    seller_name: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(1000))
    listing_title: Mapped[str | None] = mapped_column(String(1000))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # V1.2 adaptive polling: how often to re-collect + when it last ran
    poll_interval_seconds: Mapped[int | None] = mapped_column(Integer, default=14400)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    variant: Mapped[ProductVariant] = relationship(back_populates="listings")
    retailer: Mapped[Retailer] = relationship(back_populates="listings")
    observations: Mapped[list["PriceObservation"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class PriceObservation(Base):
    """Heart of the time-series store - becomes a TimescaleDB hypertable."""

    __tablename__ = "price_observations"
    __table_args__ = (
        Index("ix_price_obs_listing_time", "listing_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listings.id"), index=True
    )

    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    mrp: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shipping: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)
    coupon_discount: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)
    bank_discount: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)

    effective_price: Mapped[float | None] = mapped_column(Numeric(12, 2), index=True)

    availability: Mapped[str | None] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )

    rating: Mapped[float | None] = mapped_column(Numeric(4, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    delivery_estimate: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(64))
    source_metadata: Mapped[dict | None] = mapped_column(JSONType, default=dict)

    quality_score: Mapped[float | None] = mapped_column(Numeric(6, 4))
    trust_tier: Mapped[str | None] = mapped_column(String(16))  # TRUSTED / REVIEW / QUARANTINED

    listing: Mapped[Listing] = relationship(back_populates="observations")


class Prediction(Base):
    """Every forecast is persisted so the AI's history is reconstructible."""

    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_variant_time", "product_variant_id", "generated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), index=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon_hours: Mapped[int] = mapped_column(Integer)

    p05: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p10: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p25: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p50: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p75: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p90: Mapped[float | None] = mapped_column(Numeric(12, 2))
    p95: Mapped[float | None] = mapped_column(Numeric(12, 2))

    probability_below_target: Mapped[float | None] = mapped_column(Numeric(8, 6))
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2))

    confidence_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    model_version: Mapped[str | None] = mapped_column(String(64))
    # V1.2 prediction ledger: which calibration artifact + which retailer's market
    calibration_version: Mapped[str | None] = mapped_column(String(64))
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retailers.id"), nullable=True
    )
    calibration_key_used: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Event(Base):
    """Event calendar: sales, launches, festivals - causal/event layer."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(500))
    event_type: Mapped[str] = mapped_column(String(64), index=True)  # SALE, LAUNCH, FESTIVAL...
    scope: Mapped[str] = mapped_column(String(64), default="GLOBAL")  # GLOBAL/RETAILER/CATEGORY
    category: Mapped[str | None] = mapped_column(String(255), index=True)
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retailers.id"), nullable=True
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), index=True
    )
    target_price: Mapped[float] = mapped_column(Numeric(12, 2))
    direction: Mapped[str] = mapped_column(String(16), default="below")  # below | at
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="alerts")


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="watchlist")


class RawObservation(Base):
    """Unprocessed collector payload. Nothing touches a trusted table before this is vetted."""

    __tablename__ = "raw_observations"
    __table_args__ = (
        Index("ix_raw_obs_listing_time", "listing_id", "collected_at"),
        Index("ix_raw_obs_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    source: Mapped[str] = mapped_column(String(64), index=True)
    collector_run_id: Mapped[str | None] = mapped_column(String(64))
    listing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("listings.id"), nullable=True)
    retailer_name: Mapped[str | None] = mapped_column(String(255))
    identity: Mapped[dict | None] = mapped_column(JSONType, default=dict)  # title, gtin, sku, model...
    payload: Mapped[dict | None] = mapped_column(JSONType, default=dict)  # full scraped state
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    status: Mapped[str] = mapped_column(String(16), default="RAW")  # RAW/VALIDATED/QUARANTINED/VERIFIED
    validation_errors: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    anomaly_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    anomaly_reasons: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    anomaly_status: Mapped[str | None] = mapped_column(String(16))  # CHECKED / CONFIRMED / REJECTED
    quality_score: Mapped[float | None] = mapped_column(Numeric(6, 4))
    match_confidence: Mapped[float | None] = mapped_column(Numeric(8, 6))
    match_method: Mapped[str | None] = mapped_column(String(64))
    resolved_listing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("listings.id"), nullable=True)


class SystemEvent(Base):
    """Persisted event log: replayable stream + monitoring/audit source of truth."""

    __tablename__ = "system_events"
    __table_args__ = (
        Index("ix_system_events_type_time", "event_type", "occurred_at"),
        Index("ix_system_events_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSONType, default=dict)


class MatchCandidate(Base):
    """Product-identity matches needing human/secondary verification (0.95 <= score < 0.995)."""

    __tablename__ = "match_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    raw_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_observations.id"), nullable=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("listings.id"), nullable=True)
    suggested_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id"), nullable=True
    )
    identity: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    score: Mapped[float] = mapped_column(Numeric(8, 6))
    method: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING/APPROVED/REJECTED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelRegistryEntry(Base):
    """Champion/challenger lifecycle. Statuses: EXPERIMENT/CANDIDATE/SHADOW/CHAMPION/RETIRED."""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    model_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="EXPERIMENT", index=True)
    model_type: Mapped[str | None] = mapped_column(String(64))  # ensemble/gbm/statistical...
    category: Mapped[str | None] = mapped_column(String(255))
    horizon_hours: Mapped[int | None] = mapped_column(Integer)
    features_version: Mapped[str | None] = mapped_column(String(32))
    calibration_version: Mapped[str | None] = mapped_column(String(32))
    conformal_version: Mapped[str | None] = mapped_column(String(32))
    metrics: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    metadata_: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class PredictionOutcome(Base):
    """Actual result per forecast - the raw material of the reliability contract."""

    __tablename__ = "prediction_outcomes"
    __table_args__ = (
        Index("ix_prediction_outcomes_prediction", "prediction_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("predictions.id"), index=True
    )
    actual_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    actual_effective_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    realized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    in_interval: Mapped[bool | None] = mapped_column(Boolean)  # p50-based 90% interval
    error_median: Mapped[float | None] = mapped_column(Numeric(12, 2))
    error_abs: Mapped[float | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConversationState(Base):
    """Persistent conversational planning state for the AI agent (V1.2).

    Carries constraints from earlier turns (max_price, requirements, wait
    horizon, strategy) so "under Rs 80k" + "I can wait two months" + "RTX 5060"
    accumulate into one intent spec instead of being lost between turns.
    """

    __tablename__ = "conversation_states"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationTrace(Base):
    """Append-only per-turn trace of the AI agent (V2).

    One row per chat turn: intent, required plan, backend used (deterministic /
    llm / llm-fallback), every typed tool call with its arguments, the step
    trail with summaries and details (the AI's reasoning), the final reply, and
    latency. Errors are traced too (error column) so the admin surface can see
    how the planner degrades.
    """

    __tablename__ = "conversation_traces"
    __table_args__ = (
        Index("ix_conversation_traces_conv", "conversation_id", "turn_index"),
        Index("ix_conversation_traces_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    turn_index: Mapped[int] = mapped_column(Integer, default=1)
    intent: Mapped[str | None] = mapped_column(String(32))
    backend: Mapped[str | None] = mapped_column(String(32))
    requires: Mapped[list] = mapped_column(JSONType, default=list)
    tool_calls: Mapped[list] = mapped_column(JSONType, default=list)
    steps: Mapped[list] = mapped_column(JSONType, default=list)
    reply: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ShoppingSession(Base):
    """A user-controlled purchase workflow (V1.2).

    Status machine: SEARCHING -> SELECTED -> PRICE_VERIFIED -> CHECKOUT_READY
    -> USER_CONFIRMED -> ORDER_PLACED -> TRACKING -> COMPLETED.
    Two explicit confirmations: (1) choose an offer, (2) approve final total.
    """

    __tablename__ = "shopping_sessions"
    __table_args__ = (
        Index("ix_shopping_sessions_user", "user_id"),
        Index("ix_shopping_sessions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64))
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), index=True
    )
    selected_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listings.id"), nullable=True
    )
    strategy: Mapped[str] = mapped_column(String(32), default="IMMEDIATE")
    status: Mapped[str] = mapped_column(String(32), default="SEARCHING")
    checkout_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    delivery_estimate: Mapped[str | None] = mapped_column(String(255))
    selected_offer: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    provider_session_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    selected_listing: Mapped[Listing | None] = relationship()


class PurchaseOrder(Base):
    """Order placed through a retailer-permitted PurchaseProvider (V1.2)."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_purchase_orders_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_sessions.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64))
    retailer_name: Mapped[str | None] = mapped_column(String(255))
    order_ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="TRACKING")
    total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    tracking_url: Mapped[str | None] = mapped_column(String(1000))
    last_status: Mapped[str | None] = mapped_column(String(500))
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
