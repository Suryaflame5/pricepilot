"""Price collectors: pluggable interfaces for scraping/pulling retailer prices."""

from price_engine.collectors.base import CollectionResult, Collector, CollectorError
from price_engine.collectors.mock import MockCollector

__all__ = ["CollectionResult", "Collector", "CollectorError", "MockCollector"]
