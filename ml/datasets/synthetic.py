"""Synthetic retail price series generator.

Simulates: baseline price + weekly seasonality + slow drift + random
promotions (coupon windows) + big sale dips + noise. Used for development,
CI and backtest experiments until real scraped data accumulates.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

PRODUCT_TEMPLATES = [
    {"brand": "Sony", "model": "WH-1000XM6", "category": "headphones", "base_price": 29990, "mrp": 39990},
    {"brand": "Apple", "model": "iPhone 16", "category": "smartphones", "base_price": 79900, "mrp": 89900},
    {"brand": "Samsung", "model": "Galaxy S25 Ultra", "category": "smartphones", "base_price": 129999, "mrp": 149999},
    {"brand": "Boat", "model": "Airdopes 141", "category": "earbuds", "base_price": 1299, "mrp": 2999},
    {"brand": "Dell", "model": "XPS 16", "category": "laptops", "base_price": 184990, "mrp": 219990},
]

RETAILERS = [
    {"name": "Amazon India", "domain": "amazon.in"},
    {"name": "Flipkart", "domain": "flipkart.com"},
    {"name": "Croma", "domain": "croma.com"},
    {"name": "Reliance Digital", "domain": "reliancedigital.in"},
]


@dataclass
class SyntheticSeries:
    series: pd.Series
    meta: dict = field(default_factory=dict)


def generate_series(
    base_price: float = 29990.0,
    days: int = 365,
    obs_per_day: int = 4,
    seed: int = 42,
    promo_intensity: float = 1.0,
) -> SyntheticSeries:
    rng = np.random.default_rng(seed)
    hours = days * 24
    t = np.arange(hours)

    # baseline: slow seasonal drift + noise floor
    trend = base_price * (1 + 0.12 * np.sin(2 * np.pi * t / (365 * 24) + 0.5))
    weekly = base_price * 0.015 * np.sin(2 * np.pi * t / (7 * 24))

    # promotions: 3-5 day coupon windows every ~35 days, 3-10% off
    promo = np.zeros(hours)
    start = rng.integers(0, 7 * 24)
    while start < hours:
        length = int(rng.integers(3, 5) * 24)
        depth = rng.uniform(0.03, 0.10) * promo_intensity
        promo[start : start + length] = depth
        start += int(rng.integers(25, 45) * 24)

    # big sale events (Diwali/Black Friday style): 10-18% dips for 5 days
    sale = np.zeros(hours)
    for offset_days in (45, 150, 260, 320):
        center = offset_days * 24
        if center > hours:
            continue
        depth = rng.uniform(0.10, 0.18)
        s, e = max(0, center - 2 * 24), min(hours, center + 3 * 24)
        sale[s:e] = depth

    noise = rng.normal(0, base_price * 0.004, hours)
    price = (trend + weekly) * (1 - promo - sale) + noise

    # sample at obs_per_day intervals
    idx = np.arange(0, hours, 24 // obs_per_day)
    end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(end=end, periods=len(idx), freq=f"{24 // obs_per_day}h")
    values = np.maximum(price[idx], base_price * 0.6)

    return SyntheticSeries(
        series=pd.Series(values, index=index),
        meta={
            "base_price": base_price,
            "days": days,
            "obs_per_day": obs_per_day,
            "promo_intensity": promo_intensity,
        },
    )


def make_records(
    products: int = 5,
    days: int = 365,
    obs_per_day: int = 4,
    seed: int = 7,
) -> dict:
    """Build ready-to-insert record bundles: products, variants, retailers,
    listings, observations, events."""
    rng = np.random.default_rng(seed)
    retailer_ids = [uuid.uuid4() for _ in RETAILERS]

    products_out = []
    variants_out = []
    listings_out = []
    observations_out = []
    events_out = []

    for i, template in enumerate(PRODUCT_TEMPLATES[:products]):
        product_id = uuid.uuid4()
        variant_id = uuid.uuid4()
        products_out.append(
            {
                "id": product_id,
                "brand": template["brand"],
                "model": template["model"],
                "canonical_name": f"{template['brand']} {template['model']}",
                "category": template["category"],
                "subcategory": template["category"],
                "launched_at": datetime.utcnow() - timedelta(days=300),
            }
        )
        variants_out.append(
            {
                "id": variant_id,
                "product_id": product_id,
                "variant_name": f"{template['brand']} {template['model']} - Black",
                "color": "Black",
                "condition": "new",
            }
        )

        for j, rid in enumerate(retailer_ids[: rng.integers(2, 4)]):
            listing_id = uuid.uuid4()
            listings_out.append(
                {
                    "id": listing_id,
                    "product_variant_id": variant_id,
                    "retailer_id": rid,
                    "seller_name": RETAILERS[retailer_ids.index(rid)]["name"],
                    "url": f"https://{RETAILERS[retailer_ids.index(rid)]['domain']}/p/{variant_id}",
                    "listing_title": variants_out[-1]["variant_name"],
                    "active": True,
                }
            )
            gen = generate_series(
                base_price=template["base_price"] * rng.uniform(0.97, 1.03),
                days=days,
                obs_per_day=obs_per_day,
                seed=seed + i * 10 + j,
                promo_intensity=rng.uniform(0.7, 1.3),
            )
            s = gen.series
            mrp = template["mrp"]
            for ts, v in s.items():
                coupon = round(v * rng.uniform(0, 0.05), 2) if rng.random() < 0.3 else 0.0
                bank = round(v * 0.05, 2) if rng.random() < 0.25 else 0.0
                observations_out.append(
                    {
                        "listing_id": listing_id,
                        "price": round(float(v), 2),
                        "mrp": mrp,
                        "shipping": 0.0,
                        "coupon_discount": coupon,
                        "bank_discount": bank,
                        "effective_price": round(float(v) - coupon - bank, 2),
                        "availability": "IN_STOCK" if rng.random() > 0.02 else "OUT_OF_STOCK",
                        "observed_at": ts,
                    }
                )

    events_out = [
        {"name": "Great Indian Festival", "event_type": "SALE", "scope": "RETAILER", "retailer_id": retailer_ids[0], "category": None, "starts_at": datetime.utcnow() + timedelta(days=6), "ends_at": datetime.utcnow() + timedelta(days=11)},
        {"name": "Diwali", "event_type": "FESTIVAL", "scope": "GLOBAL", "category": None, "starts_at": datetime.utcnow() + timedelta(days=45), "ends_at": datetime.utcnow() + timedelta(days=50)},
        {"name": "Black Friday", "event_type": "SALE", "scope": "RETAILER", "retailer_id": retailer_ids[1], "category": None, "starts_at": datetime.utcnow() + timedelta(days=90), "ends_at": datetime.utcnow() + timedelta(days=95)},
        {"name": "Republic Day Sale", "event_type": "SALE", "scope": "GLOBAL", "category": None, "starts_at": datetime.utcnow() + timedelta(days=120), "ends_at": datetime.utcnow() + timedelta(days=124)},
    ]

    return {
        "retailers": [{"id": rid, "name": r["name"], "domain": r["domain"], "currency": "INR"} for rid, r in zip(retailer_ids, RETAILERS)],
        "products": products_out,
        "variants": variants_out,
        "listings": listings_out,
        "observations": observations_out,
        "events": events_out,
    }
