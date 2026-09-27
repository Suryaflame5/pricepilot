"""API smoke test: boots FastAPI against SQLite, seeds synthetic data,
exercises the main endpoints end-to-end (blueprint sections 21-24).

Run:  python -m pytest tests/test_api_smoke.py -v
"""

import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_smoke.db"
os.environ["MODEL_REGISTRY_DIR"] = "ml/model_registry"
os.environ["CALIBRATION_STORE_DIR"] = "ml/model_registry/calibration"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database.models import Listing, Product, ProductVariant, Retailer
from database.session import create_engine, create_session_factory, init_db
from ml.datasets.seed_db import seed


@pytest.fixture(scope="module")
def client():
    db_file = os.environ["DATABASE_URL"].rsplit("/", 1)[-1]
    if os.path.exists(db_file):
        os.remove(db_file)
    engine = create_engine(os.environ["DATABASE_URL"])
    import asyncio

    asyncio.get_event_loop().run_until_complete(init_db(engine))
    factory = create_session_factory(engine)
    asyncio.get_event_loop().run_until_complete(seed(factory(), products=2, days=180, obs_per_day=2))

    from api.main import app

    with TestClient(app) as c:
        yield c
    from api import dependencies

    asyncio.get_event_loop().run_until_complete(engine.dispose())
    asyncio.get_event_loop().run_until_complete(dependencies.engine.dispose())
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def _first_variant_id(engine_url: str) -> str:
    import asyncio

    engine = create_engine(engine_url)
    factory = create_session_factory(engine)

    async def _get():
        async with factory() as db:
            variant = (await db.execute(select(ProductVariant))).scalars().first()
            return str(variant.id)

    vid = asyncio.get_event_loop().run_until_complete(_get())
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return vid


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_search_products(client):
    resp = client.get("/products/search", params={"q": "Sony"})
    assert resp.status_code == 200
    products = resp.json()
    assert len(products) >= 1
    assert "canonical_name" in products[0]


def test_compare(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    resp = client.get(f"/products/variant/{vid}/compare")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cheapest"] is not None
    assert data["offers"][0]["effective_price"] == data["cheapest"]["effective_price"]


def test_get_variant(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    resp = client.get(f"/products/variant/{vid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == vid
    assert data["product"] is not None
    assert "canonical_name" in data["product"]


def test_price_stats(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    import asyncio

    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)

    async def _get_listing():
        async with factory() as db:
            listing = (await db.execute(select(Listing))).scalars().first()
            return str(listing.id)

    lid = asyncio.get_event_loop().run_until_complete(_get_listing())
    asyncio.get_event_loop().run_until_complete(engine.dispose())

    resp = client.get("/prices/stats", params={"listing_id": lid})
    assert resp.status_code == 200
    assert resp.json()["observations_90d"] > 0


def test_price_prediction(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    resp = client.post("/predictions/price", json={"product_variant_id": vid, "horizon_hours": 720})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["forecast"]["p50"] > 0
    assert data["interval"]["lower"] < data["interval"]["upper"]
    assert data["confidence"]["level"] in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")
    assert data["per_model"]


def test_target_probability(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    resp = client.post(
        "/predictions/target",
        json={"product_variant_id": vid, "target_price": 10000, "horizons_hours": [720, 2160]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data["probabilities"]) == {"30d", "90d"}


def test_decision(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    resp = client.post(
        "/predictions/decision",
        json={"product_variant_id": vid, "target_price": 10000, "urgency": "normal"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["recommendation"] in ("BUY_NOW", "WAIT", "INSUFFICIENT_CONFIDENCE")


def test_chat(client):
    resp = client.post("/chat", json={"message": "cheapest Sony headphones"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["reply"]
    assert data["steps"]


def test_alerts(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    create = client.post("/alerts", json={"product_variant_id": vid, "target_price": 5000})
    assert create.status_code == 201
    alert_id = create.json()["id"]

    listing = client.get("/alerts")
    assert listing.status_code == 200
    assert any(a["id"] == alert_id for a in listing.json())

    resp = client.post("/alerts/check")
    assert resp.status_code == 200
    assert resp.json()["checked"] >= 1

    deleted = client.delete(f"/alerts/{alert_id}")
    assert deleted.status_code == 204


def test_ingest_observation(client):
    import asyncio

    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)

    async def _get_listing():
        async with factory() as db:
            listing = (await db.execute(select(Listing))).scalars().first()
            return str(listing.id)

    lid = asyncio.get_event_loop().run_until_complete(_get_listing())
    asyncio.get_event_loop().run_until_complete(engine.dispose())

    resp = client.post(
        "/prices/observations",
        json={"listing_id": lid, "price": 29999, "coupon_discount": 999},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["effective_price"] == 29000.0


def test_raw_ingest_pipeline(client):
    """V1.1 intake: raw observation -> quality screening -> events."""
    resp = client.post(
        "/prices/ingest",
        json={
            "source": "croma",
            "source_mode": "page",
            "retailer": "croma",
            "title": "Sony WH-1000XM5 Wireless Headphones",
            "price": 27022,
            "mrp": 34990,
            "availability": "IN_STOCK",
            "rating": 4.6,
            "review_count": 1205,
            "identity": {"brand": "Sony", "model": "WH-1000XM5", "gtin": "4548736117576"},
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "VERIFIED"
    assert data["quality"]["tier"] in ("TRUSTED", "REVIEW")
    assert data["listing_id"] is not None


def test_raw_ingest_quarantines_garbage(client):
    resp = client.post(
        "/prices/ingest",
        json={
            "source": "flipkart",
            "source_mode": "page",
            "retailer": "flipkart",
            "price": None,
            "availability": "IN_STOCK",
            "identity": {"gtin": "0000000000000"},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "QUARANTINED"
    assert "price_missing" in data["reasons"] or "price_nonpositive" in data["reasons"]


def test_matching_candidates(client):
    resp = client.get("/matching/candidates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_monitoring_endpoints(client):
    for path in ("/monitoring/coverage", "/monitoring/registry", "/monitoring/calibration"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_three_part_confidence_surface(client):
    vid = _first_variant_id(os.environ["DATABASE_URL"])
    resp = client.post("/predictions/price", json={"product_variant_id": vid, "horizon_hours": 720})
    assert resp.status_code == 200, resp.text
    conf = resp.json()["confidence"]
    assert conf["forecast_confidence"] is not None
    assert conf["model_reliability"] is not None
    assert conf["data_reliability"] is not None
    assert conf["weights"]["forecast"] == 0.40
