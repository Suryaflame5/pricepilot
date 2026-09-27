"""Database package: models + async session management."""

from database.models import (
    Base,
    Event,
    Listing,
    MatchCandidate,
    ModelRegistryEntry,
    Prediction,
    PredictionOutcome,
    PriceAlert,
    PriceObservation,
    Product,
    ProductVariant,
    RawObservation,
    Retailer,
    SystemEvent,
    User,
    WatchlistItem,
)
from database.session import create_engine, create_session_factory, init_db

__all__ = [
    "Base",
    "Event",
    "Listing",
    "MatchCandidate",
    "ModelRegistryEntry",
    "Prediction",
    "PredictionOutcome",
    "PriceAlert",
    "PriceObservation",
    "Product",
    "ProductVariant",
    "RawObservation",
    "Retailer",
    "SystemEvent",
    "User",
    "WatchlistItem",
    "create_engine",
    "create_session_factory",
    "init_db",
]
