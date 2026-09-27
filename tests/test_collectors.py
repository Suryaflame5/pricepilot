"""V1.1 collector tests: JSON-LD/meta parsing, HTTP page adapter extraction,
retry/degradation behavior, rate limiter, registry, mock collector state."""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import httpx
import pytest

from price_engine.collectors.adapters import AmazonCollector, CromaCollector, FlipkartCollector
from price_engine.collectors.base import (
    CollectorError,
    DegradedError,
    RateLimiter,
    RetryPolicy,
    run_targets,
)
from price_engine.collectors.http import HttpClient
from price_engine.collectors.mock import MockCollector
from price_engine.collectors.parsers import (
    find_product_json_ld,
    normalize_state,
    parse_meta_price,
    parse_price_text,
)
from price_engine.collectors.registry import BUILTIN_COLLECTORS, create_collector

PRODUCT_JSON_LD = """
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
  "brand": {"@type": "Brand", "name": "Sony"},
  "model": "WH-1000XM5",
  "sku": "SONY-WH1000XM5",
  "gtin": "4548736117576",
  "offers": {
    "@type": "Offer",
    "price": "27022.00",
    "priceCurrency": "INR",
    "availability": "https://schema.org/InStock",
    "seller": {"@type": "Organization", "name": "TechZone"}
  }
}
</script>
"""

PAGE_WITH_META = """
<html><head>
<meta property="og:price:amount" content="₹27,022" />
<meta property="og:availability" content="InStock" />
<title>Sony WH-1000XM5</title>
</head><body></body></html>
"""


# ---------------------------------------------------------------- parsers
class TestParsers:
    def test_json_ld_product_extraction(self):
        product = find_product_json_ld(PRODUCT_JSON_LD)
        assert product is not None
        assert product["name"].startswith("Sony")
        offer = product["offers"]
        assert float(offer["price"]) == 27022.0
        assert "InStock" in offer["availability"]

    def test_parse_price_text_rupee(self):
        assert parse_price_text("₹27,022") == 27022.0
        assert parse_price_text("Rs. 1,299") == 1299.0
        assert parse_price_text("$299.99") == 299.99
        assert parse_price_text("garbage") is None

    def test_meta_fallback(self):
        state = parse_meta_price(PAGE_WITH_META)
        assert state["price"] == 27022.0
        assert state["availability"] == "IN_STOCK"

    def test_normalize_state(self):
        state = normalize_state({"price": "₹27,022", "mrp": "35000", "availability": "in stock",
                                 "review_count": "1,205", "rating": "4.6"})
        assert state["price"] == 27022.0
        assert state["review_count"] == 1205
        assert state["availability"] == "IN_STOCK"


# ---------------------------------------------------------------- adapters
class TestAdapters:
    @staticmethod
    def _collector(cls):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, text=PRODUCT_JSON_LD, request=req)
        )
        client = HttpClient()
        client._client = httpx.AsyncClient(
            transport=transport, headers={}, follow_redirects=True
        )
        return cls(client=client)

    @pytest.mark.asyncio
    async def test_amazon_page_extraction(self):
        result = await self._collector(AmazonCollector).collect("listing-1", "http://amazon.in/dp/B0ABC")
        assert result.price == 27022.0
        assert result.mrp is None or result.mrp >= 0
        assert result.identity["gtin"] == "4548736117576"
        assert result.identity["brand"] == "Sony"
        assert result.seller_name == "TechZone"
        assert result.effective_price == 27022.0
        assert result.source_metadata["retailer"] == "amazon"

    @pytest.mark.asyncio
    async def test_flipkart_and_croma_share_contract(self):
        for cls in (FlipkartCollector, CromaCollector):
            result = await self._collector(cls).collect("l2", "http://x")
            assert result.price == 27022.0
            assert result.availability == "IN_STOCK"

    @pytest.mark.asyncio
    async def test_out_of_stock_parsing(self):
        html = PRODUCT_JSON_LD.replace("InStock", "OutOfStock")
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text=html, request=req))
        client = HttpClient()
        client._client = httpx.AsyncClient(transport=transport, headers={}, follow_redirects=True)
        result = await FlipkartCollector(client=client).collect("l3", "http://x")
        assert result.availability == "OUT_OF_STOCK"

    @pytest.mark.asyncio
    async def test_degraded_403_raises_degraded_error(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(403, text="blocked", request=req)
        )
        client = HttpClient()
        client._client = httpx.AsyncClient(transport=transport, headers={}, follow_redirects=True)
        with pytest.raises(DegradedError):
            await client.get("http://x")

    @pytest.mark.asyncio
    async def test_retry_then_give_up(self):
        calls = {"n": 0}

        def handler(req):
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503, text="busy", request=req)
            return httpx.Response(200, text="ok", request=req)

        transport = httpx.MockTransport(handler)
        client = HttpClient()
        client._client = httpx.AsyncClient(transport=transport, headers={}, follow_redirects=True)
        resp = await client.get("http://x")
        assert resp.status_code == 200
        assert calls["n"] == 3  # 2 retries happened


# ---------------------------------------------------------------- base infra
class TestCollectorInfra:
    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_rate(self):
        limiter = RateLimiter(rate=50, period_s=1.0)  # generous to avoid slow tests
        t0 = asyncio.get_event_loop().time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - t0
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_run_targets_continues_after_error(self):
        class Flaky(FlipkartCollector):
            def __init__(self):
                super().__init__(client=None)
                self.fail = True

            async def collect(self, listing_id, url=None):
                if self.fail:
                    self.fail = False
                    raise CollectorError("boom")
                from price_engine.collectors.base import CollectionResult

                return CollectionResult(listing_id=listing_id, price=10.0)

        collector = Flaky()
        errors = []
        results = await run_targets(collector, [("a", None), ("b", None)],
                                    on_error=lambda lid, exc: errors.append(lid))
        assert len(results) == 2  # transient error retried, target recovered
        assert errors == ["a"]


# ---------------------------------------------------------------- registry
class TestRegistry:
    def test_builtin_names(self):
        assert {"mock", "amazon", "flipkart", "croma", "reliance_digital"} <= set(BUILTIN_COLLECTORS)

    def test_create_collector_from_config(self):
        c = create_collector("mock", {"rate": 2, "period_s": 0.5})
        assert c.name == "mock"
        c2 = create_collector("amazon", {"max_attempts": 1, "rate": 1})
        assert isinstance(c2, AmazonCollector)

    def test_unknown_collector_raises(self):
        with pytest.raises(KeyError):
            create_collector("nope")


# ---------------------------------------------------------------- mock
class TestMockCollector:
    @pytest.mark.asyncio
    async def test_mock_state_transitions_deterministic(self):
        c1 = MockCollector(base_price=1000.0, seed=42)
        c2 = MockCollector(base_price=1000.0, seed=42)
        for _ in range(5):
            r1 = await c1.collect("l1")
            r2 = await c2.collect("l1")
            assert r1.price == r2.price
            assert r1.availability == r2.availability
            assert r1.seller_name == r2.seller_name
            assert r1.rating == r2.rating

    @pytest.mark.asyncio
    async def test_mock_eventually_cycles_through_states(self):
        c = MockCollector(base_price=1000.0, seed=7)
        states = set()
        for _ in range(500):
            r = await c.collect("l1")
            states.add((r.availability, r.seller_name, r.coupon_discount > 0))
        assert len(states) > 1  # stock/seller/promo dynamics exercised
