"""Retailer adapters.

Architecture notes (compliance-first):
- `mode="feed"`: official APIs / retailer feeds (JSON) when keys/access granted.
  Feed payloads are normalized by parsers.normalize_state - no page extraction.
- `mode="page"`: permitted public-page collection via schema.org structured data
  (JSON-LD / meta tags). This is NOT a CAPTCHA/anti-bot bypass layer; adapters
  MUST be disabled for any retailer that blocks or whose terms forbid collection.
- Retry/rate-limit/degradation handling lives in the shared HttpClient + base.Collector.
"""

from typing import Any

from price_engine.collectors.base import CollectionResult, Collector
from price_engine.collectors.http import HttpClient
from price_engine.collectors.parsers import (
    find_product_json_ld,
    normalize_state,
    parse_meta_price,
    parse_offer,
)

DEFAULT_FEED_TIMEOUT_S = 20.0


class HTTPPageCollector(Collector):
    """Structured-data page extraction, shared by all page-mode adapters."""

    name = "http"
    retailer = ""

    def __init__(
        self,
        client: HttpClient | None = None,
        url_template: str = "{url}",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._client = client or HttpClient()
        self.url_template = url_template

    async def collect(self, listing_id: str, url: str | None = None) -> CollectionResult:
        if not url:
            raise ValueError(f"page-mode collector {self.name} requires a url")
        resp = await self._client.get(self.url_template.format(url=url))
        html = resp.text

        state: dict[str, Any] = {
            "title": self._extract_title(html),
        }
        product = find_product_json_ld(html)
        if product:
            offers = product.get("offers")
            offer_state: dict[str, Any] = {}
            if isinstance(offers, dict):
                offer_state = parse_offer(offers)
            elif isinstance(offers, list) and offers:
                parsed = [parse_offer(o) for o in offers if isinstance(o, dict)]
                parsed = [p for p in parsed if p.get("price") is not None]
                if parsed:
                    offer_state = min(parsed, key=lambda p: float(p["price"]))
            state.update(offer_state)
            state["seller_name"] = self._extract_seller(product)
            identity = self._extract_identity(product)
        else:
            identity = {}

        state.update(parse_meta_price(html))
        state = normalize_state(state)

        return CollectionResult(
            listing_id=listing_id,
            price=state["price"] or 0.0,
            mrp=state["mrp"],
            shipping=state["shipping"],
            coupon_discount=state["coupon_discount"],
            bank_discount=state["bank_discount"],
            availability=state["availability"],
            seller_name=state["seller_name"],
            title=state["title"],
            identity=identity,
            raw={"state": state, "page_bytes": len(html)},
            source_metadata={
                "mode": "page",
                "retailer": self.retailer,
                "http_status": resp.status_code,
                "url": url,
            },
        )

    def _extract_title(self, html: str) -> str | None:
        return None  # overridden per retailer

    def _extract_seller(self, product: dict[str, Any]) -> str | None:
        candidates = [product.get("seller")]
        offers = product.get("offers")
        if isinstance(offers, dict):
            candidates.append(offers.get("seller"))
        elif isinstance(offers, list):
            candidates.extend(o.get("seller") for o in offers if isinstance(o, dict))
        for seller in candidates:
            if isinstance(seller, dict):
                name = seller.get("name") or seller.get("@id")
                if name:
                    return name
        return None

    def _extract_identity(self, product: dict[str, Any]) -> dict[str, Any]:
        return {
            "brand": product.get("brand", {}).get("name") if isinstance(product.get("brand"), dict) else None,
            "model": product.get("model"),
            "sku": product.get("sku"),
            "gtin": product.get("gtin") or (product.get("gtin13") or []),
            "mpn": product.get("mpn"),
        }


class AmazonCollector(HTTPPageCollector):
    name = "amazon"
    retailer = "amazon"

    async def collect(self, listing_id: str, url: str | None = None) -> CollectionResult:
        result = await super().collect(listing_id, url)
        if not result.title:
            result.title = result.identity.get("model")
        return result

    def _extract_title(self, html: str) -> str | None:
        import re

        m = re.search(r'<span id="productTitle"[^>]*>(.*?)</span>', html, re.S)
        if m:
            import html as html_mod

            return html_mod.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        return None


class FlipkartCollector(HTTPPageCollector):
    name = "flipkart"
    retailer = "flipkart"


class CromaCollector(HTTPPageCollector):
    name = "croma"
    retailer = "croma"

    def _extract_title(self, html: str) -> str | None:
        import html as html_mod
        import re

        m = re.search(r'<h1[^>]*class="[^"]*pdp-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
        if m:
            return html_mod.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        return None


class RelianceDigitalCollector(HTTPPageCollector):
    name = "reliance_digital"
    retailer = "reliance_digital"


class FeedCollector(Collector):
    """Official-feed / API adapter base. Subclass and implement `parse(payload)`.

    Example: Amazon Product Advertising API, Croma B2B feed, brand dropship feeds.
    """

    name = "feed"
    retailer = ""

    def __init__(self, api_key: str | None = None, client: HttpClient | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key
        self._client = client or HttpClient()

    async def fetch_payload(self, listing_id: str, url: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def parse(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Payload -> canonical observation state (see parsers.normalize_state)."""
        return normalize_state(payload)

    async def collect(self, listing_id: str, url: str | None = None) -> CollectionResult:
        payload = await self.fetch_payload(listing_id, url)
        state = self.parse(payload)
        return CollectionResult(
            listing_id=listing_id,
            price=state["price"] or 0.0,
            mrp=state["mrp"],
            shipping=state["shipping"],
            coupon_discount=state["coupon_discount"],
            bank_discount=state["bank_discount"],
            availability=state["availability"],
            seller_name=state["seller_name"],
            title=state["title"],
            identity=payload.get("identity", {}),
            raw={"payload": payload},
            source_metadata={"mode": "feed", "retailer": self.retailer},
        )
