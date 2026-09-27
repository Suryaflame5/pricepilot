"""Retailer page/feed parsers.

Structured-data extraction is the contract: parse JSON-LD (schema.org Product/Offer)
plus HTML meta fallbacks. Parsers are pure functions over (html, url) -> state dict,
so each retailer adapter stays a thin URL/endpoint definition + test fixture.
"""

import json
import re
from typing import Any

_SCRIPT_RE = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def extract_json_ld(html: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for m in _SCRIPT_RE.finditer(html):
        try:
            parsed = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, list):
            blocks.extend(parsed)
        elif isinstance(parsed, dict):
            blocks.append(parsed)
    return blocks


def find_product_json_ld(html: str) -> dict[str, Any] | None:
    """First schema.org Product (or @graph entry) node, prefer one with an Offer."""
    nodes = [n for n in extract_json_ld(html) if isinstance(n, dict)]
    for node in list(nodes):
        for candidate in (node.get("mainEntity"), *nodes):
            if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                if candidate.get("offers") is not None:
                    return candidate
    for node in nodes:
        if isinstance(node.get("@type"), list):
            if "Product" in node["@type"]:
                return node
    return None


def parse_offer(offer: dict[str, Any]) -> dict[str, Any]:
    price = _to_float(offer.get("price") or offer.get("lowPrice"))
    if price is None and isinstance(offer.get("priceSpecification"), dict):
        price = _to_float(offer["priceSpecification"].get("price"))
    return {
        "price": price,
        "mrp": _to_float(offer.get("highPrice") or offer.get("listPrice")),
        "availability": "OUT_OF_STOCK" if "OutOfStock" in str(offer.get("availability", "")) else "IN_STOCK",
        "currency": offer.get("priceCurrency"),
    }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"\d[\d,]*\.?\d*", str(value))
    if not m:
        return None
    cleaned = m.group(0).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_price_text(text: str) -> float | None:
    """Robust INR/number parsing: '₹27,022', 'Rs. 27,022', '27022', '$299.99'."""
    return _to_float(text)


_META_PRICE = re.compile(
    r'<meta[^>]+(?:property|itemprop)=["\'](?:og:price:amount|product:price:amount|price)["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_META_AVAIL = re.compile(
    r'<meta[^>]+(?:property|itemprop)=["\'](?:og:availability|availability)["\'][^>]+content=["\']([^"\']+)',
    re.I,
)


def parse_meta_price(html: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    m = _META_PRICE.search(html)
    if m:
        out["price"] = parse_price_text(m.group(1))
    m = _META_AVAIL.search(html)
    if m:
        out["availability"] = "OUT_OF_STOCK" if "out" in m.group(1).lower() else "IN_STOCK"
    return out


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw parsed state into canonical observation state (floats/None)."""
    result = {
        "price": _to_float(state.get("price")),
        "mrp": _to_float(state.get("mrp")),
        "shipping": _to_float(state.get("shipping")) or 0.0,
        "coupon_discount": _to_float(state.get("coupon_discount")) or 0.0,
        "bank_discount": _to_float(state.get("bank_discount")) or 0.0,
        "availability": str(state.get("availability") or "IN_STOCK").upper(),
        "seller_name": state.get("seller_name"),
        "title": state.get("title"),
        "rating": _to_float(state.get("rating")),
        "review_count": int(float(_to_float(state.get("review_count")))) if _to_float(state.get("review_count")) else None,
        "delivery_estimate": state.get("delivery_estimate"),
    }
    if result["availability"] not in ("IN_STOCK", "OUT_OF_STOCK", "PRE_ORDER"):
        result["availability"] = "IN_STOCK"
    return result
