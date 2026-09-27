"""Collector interface, hardened for V1.1.

Design contract:
- Every Collector returns a complete CollectionResult carrying ALL observed fields
  (price, effective components, seller, stock, rating, delivery...) plus
  source_metadata so the quality pipeline can audit provenance.
- Collectors never mutate DB state; they only fetch. The pipeline owns storage.
- Failures are typed: CollectorError (retryable), DegradedError (permanent block
  by retailer: captcha/blocked/rate-limit exhausted) - never retry a degraded target.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


class CollectorError(Exception):
    """Transient failure (timeout, 5xx). Safe to retry."""


class DegradedError(Exception):
    """Retailer-level block (captcha, banned, terms). Do NOT retry aggressively."""


@dataclass
class CollectionResult:
    listing_id: str
    price: float
    mrp: float | None = None
    shipping: float = 0.0
    coupon_discount: float = 0.0
    bank_discount: float = 0.0
    availability: str | None = "IN_STOCK"  # IN_STOCK / OUT_OF_STOCK / PRE_ORDER
    seller_name: str | None = None
    title: str | None = None
    rating: float | None = None
    review_count: int | None = None
    delivery_estimate: str | None = None
    identity: dict[str, Any] = field(default_factory=dict)  # gtin, sku, model, brand...
    raw: dict[str, Any] = field(default_factory=dict)  # full scraped state
    source_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def effective_price(self) -> float:
        return max(
            0.0,
            (self.price or 0.0)
            + (self.shipping or 0.0)
            - (self.coupon_discount or 0.0)
            - (self.bank_discount or 0.0),
        )

    def state(self) -> dict[str, Any]:
        """Canonical observation state stored in raw_observations.payload."""
        return {
            "price": self.price,
            "mrp": self.mrp,
            "shipping": self.shipping,
            "coupon_discount": self.coupon_discount,
            "bank_discount": self.bank_discount,
            "availability": self.availability,
            "seller_name": self.seller_name,
            "title": self.title,
            "rating": self.rating,
            "review_count": self.review_count,
            "delivery_estimate": self.delivery_estimate,
        }


class RetryPolicy:
    """Exponential backoff with jitter; caps total attempts."""

    def __init__(
        self, max_attempts: int = 3, base_delay_s: float = 1.0, max_delay_s: float = 30.0
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s

    def delay(self, attempt: int) -> float:
        if attempt <= 1:
            return 0.0
        d = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 2)))
        return d + (d * 0.2 * time.monotonic() % 1)  # jitter


class RateLimiter:
    """Token-bucket-ish limiter: at most `rate` calls per `period_s`."""

    def __init__(self, rate: int = 4, period_s: float = 1.0) -> None:
        self._rate = max(1, rate)
        self._period = max(0.01, period_s)
        self._tokens = float(self._rate)
        self._last = time.monotonic()

    def _refill(self, now: float) -> None:
        self._tokens = min(
            float(self._rate), self._tokens + (now - self._last) * (self._rate / self._period)
        )
        self._last = now

    async def acquire(self) -> None:
        now = time.monotonic()
        self._refill(now)
        if self._tokens < 1:
            need = 1 - self._tokens
            await asyncio.sleep(need * (self._period / self._rate))
            self._refill(time.monotonic())
        self._tokens -= 1


class Collector(ABC):
    """Implementations: official feeds/APIs, permitted page extraction, manual feeds."""

    name: str = "base"
    retailer: str = ""

    def __init__(
        self,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
        run_id: str | None = None,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.run_id = run_id or f"{self.name}-{int(time.time())}"

    @abstractmethod
    async def collect(self, listing_id: str, url: str | None = None) -> CollectionResult:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "retailer": self.retailer,
            "run_id": self.run_id,
            "retry_max_attempts": self.retry_policy.max_attempts,
        }


async def run_targets(
    collector: Collector,
    targets: list[tuple[str, str | None]],
    on_error: Callable[[str, Exception], Awaitable[None] | None] | None = None,
) -> list[CollectionResult]:
    """Sequential (politely rate-limited) collection across targets.

    A DegradedError stops that target and marks it permanently unavailable;
    transient errors retry per RetryPolicy then give up with on_error called.
    """
    results: list[CollectionResult] = []
    for listing_id, url in targets:
        last_err: Exception | None = None
        for attempt in range(1, collector.retry_policy.max_attempts + 1):
            try:
                await collector.rate_limiter.acquire()
                result = await collector.collect(listing_id, url)
                result.source_metadata.update(collector.describe(), attempt=attempt)
                results.append(result)
                break
            except DegradedError as exc:
                last_err = exc
                break  # never retry degraded targets
            except CollectorError as exc:
                last_err = exc
                if attempt < collector.retry_policy.max_attempts:
                    await asyncio.sleep(collector.retry_policy.delay(attempt))
                continue
        if last_err is not None and on_error is not None:
            cb = on_error(listing_id, last_err)
            if hasattr(cb, "__await__"):
                await cb
    return results


class CollectorScheduler:
    """Periodic loop: every `interval_s` (+jitter) re-runs the target set.

    Healthy for moderate target counts; scale out to distributed jobs later.
    """

    def __init__(self, collector: Collector, interval_s: float = 900.0, jitter_s: float = 30.0) -> None:
        self.collector = collector
        self.interval_s = interval_s
        self.jitter_s = jitter_s
        self._stop = asyncio.Event()
        self._on_results: Callable[[list[CollectionResult]], Awaitable[None] | None] | None = None

    def set_sink(self, fn: Callable[[list[CollectionResult]], Awaitable[None] | None]) -> None:
        self._on_results = fn

    async def _run_round(self, targets: list[tuple[str, str | None]]) -> None:
        results = await run_targets(self.collector, targets)
        if results and self._on_results is not None:
            cb = self._on_results(results)
            if hasattr(cb, "__await__"):
                await cb

    async def start(self, targets: list[tuple[str, str | None]]) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            round_started = time.monotonic()
            await self._run_round(targets)
            jitter = (time.monotonic() % 1) * self.jitter_s
            await asyncio.wait_for(
                self._stop.wait(), timeout=max(0.5, self.interval_s + jitter - (time.monotonic() - round_started))
            )

    def stop(self) -> None:
        self._stop.set()
