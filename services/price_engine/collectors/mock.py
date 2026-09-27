"""Deterministic mock collector for development and CI.

Generates plausible prices (with promo/discount/seller/stock dynamics) so the whole
V1.1 pipeline (quality, anomaly, change detection, events) is exercisable without
live retailer integrations.
"""

import random
from typing import Any

from price_engine.collectors.base import CollectionResult, Collector

SELLERS = ["RetailNet", "TechZone", "GlobalTrade", "PrimeSellers"]


class MockCollector(Collector):
    name = "mock"
    retailer = "mock"

    def __init__(self, base_price: float = 1000.0, seed: int = 42, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._base_price = base_price
        self._rng = random.Random(seed)
        self._seller = SELLERS[0]
        self._in_stock = True
        self._coupon_active = False
        self._rating = 4.3
        self._review_count = 120

    async def collect(self, listing_id: str, url: str | None = None) -> CollectionResult:
        drift = self._rng.gauss(0, 0.005)

        # slow state transitions so change-detection tests stay deterministic
        if self._rng.random() < 0.02:
            self._seller = SELLERS[self._rng.randrange(len(SELLERS))]
        if self._rng.random() < 0.02:
            self._in_stock = not self._in_stock
        if self._rng.random() < 0.05:
            self._coupon_active = not self._coupon_active
        if self._rng.random() < 0.03:
            self._rating = round(min(5.0, max(3.0, self._rating + self._rng.uniform(-0.2, 0.2))), 2)
        if self._rng.random() < 0.05:
            self._review_count += self._rng.randrange(1, 12)

        coupon = round(self._base_price * self._rng.uniform(0.03, 0.10), 2) if self._coupon_active else 0.0
        price = round(self._base_price * (1 + drift), 2)

        return CollectionResult(
            listing_id=listing_id,
            price=price,
            mrp=round(self._base_price * 1.3, 2),
            shipping=0.0,
            coupon_discount=coupon,
            bank_discount=0.0,
            availability="IN_STOCK" if self._in_stock else "OUT_OF_STOCK",
            seller_name=self._seller,
            title="Mock Product X1000",
            rating=self._rating,
            review_count=self._review_count,
            delivery_estimate="3-5 business days",
            identity={"model": "X1000", "brand": "MockBrand", "sku": f"MOCK-{listing_id[:8]}"},
            raw={"source": "mock", "seed_state": self._rng.getstate() and 0},
        )
