"""Collector registry: name -> factory, plus config helpers.

Config example (services/price_engine/config/collectors.yml or env):
    collectors:
      amazon:
        mode: page
        enabled: false          # compliance gate: enable only with permission/feeds
        rate: 2
        period_s: 3.0
      croma:
        mode: feed
        api_key_env: CROMA_FEED_KEY
"""

import os
from typing import Any

from price_engine.collectors.adapters import (
    AmazonCollector,
    CromaCollector,
    FeedCollector,
    FlipkartCollector,
    HTTPPageCollector,
    RelianceDigitalCollector,
)
from price_engine.collectors.base import Collector, RateLimiter, RetryPolicy
from price_engine.collectors.mock import MockCollector

BUILTIN_COLLECTORS: dict[str, type[Collector]] = {
    "mock": MockCollector,
    "amazon": AmazonCollector,
    "flipkart": FlipkartCollector,
    "croma": CromaCollector,
    "reliance_digital": RelianceDigitalCollector,
}


def create_collector(
    name: str,
    config: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> Collector:
    """Instantiate a collector from {name, mode, rate, period_s, max_attempts, api_key_env}."""
    config = config or {}
    cls = BUILTIN_COLLECTORS.get(name)
    if cls is None:
        raise KeyError(f"unknown collector '{name}'; known: {sorted(BUILTIN_COLLECTORS)}")

    kwargs: dict[str, Any] = {
        "retry_policy": RetryPolicy(max_attempts=int(config.get("max_attempts", 3))),
        "rate_limiter": RateLimiter(
            rate=int(config.get("rate", 4)), period_s=float(config.get("period_s", 1.0))
        ),
        "run_id": run_id,
    }
    mode = config.get("mode", "page")
    if issubclass(cls, HTTPPageCollector):
        if mode == "feed":
            kwargs["client"] = None  # feed collector uses its own fetch path
        return cls(**kwargs)

    if issubclass(cls, FeedCollector):
        key_env = config.get("api_key_env")
        kwargs["api_key"] = os.environ.get(key_env) if key_env else None
        return cls(**kwargs)

    return cls(**kwargs)


def collector_names() -> list[str]:
    return sorted(BUILTIN_COLLECTORS)
