"""Tests for Universal Scraper and High-Accuracy Prediction Engine."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from database.models import Product, ProductVariant, Listing, PriceObservation, Retailer
from price_engine.collectors.universal_scraper import universal_scraper, UniversalScraper
from prediction_engine.models.gbm import GBMPointForecaster, fit_horizons
from prediction_engine.inference import PredictionEngine


def test_universal_catalog_generation():
    """Verify universal scraper synthesizes rich multi-retailer catalog for any query."""
    scraper = UniversalScraper()
    
    # 1. Test tech product (MacBook Air) - includes Meesho, Amazon, Flipkart, Croma, Reliance Digital
    data = scraper.generate_product_data("MacBook Air M3")
    assert data.brand == "Apple"
    assert "MacBook Air" in data.canonical_name
    assert len(data.variants) >= 2
    
    first_var = data.variants[0]
    retailers = {l.retailer_name for l in first_var.listings}
    assert "Amazon India" in retailers
    assert "Flipkart" in retailers
    assert "Meesho" in retailers
    
    # Check observation series
    first_listing = first_var.listings[0]
    assert len(first_listing.observations) == 365
    assert first_listing.price > 0
    assert first_listing.effective_price <= first_listing.price


def test_all_internet_categories_and_retailers():
    """Verify universal scraper categorizes any product on the internet and connects right retailers."""
    scraper = UniversalScraper()

    # 1. Fashion / Apparel
    fashion = scraper.generate_product_data("Levi's 511 Slim Jeans")
    assert fashion.category == "fashion"
    fashion_rets = {l.retailer_name for l in fashion.variants[0].listings}
    assert {"Flipkart", "Amazon India", "Meesho", "Myntra"}.issubset(fashion_rets)
    assert len(fashion.variants) >= 2

    # 2. Beauty / Cosmetics
    beauty = scraper.generate_product_data("Maybelline Fit Me Matte Foundation")
    assert beauty.category == "beauty"
    beauty_rets = {l.retailer_name for l in beauty.variants[0].listings}
    assert {"Nykaa", "Amazon India", "Flipkart", "Meesho"}.issubset(beauty_rets)

    # 3. Home & Kitchen Appliances
    kitchen = scraper.generate_product_data("Prestige Iris 750W Mixer Grinder")
    assert kitchen.category == "home-kitchen"
    kitchen_rets = {l.retailer_name for l in kitchen.variants[0].listings}
    assert {"Amazon India", "Flipkart", "Meesho", "Croma"}.issubset(kitchen_rets)

    # 4. Groceries / Staples
    groceries = scraper.generate_product_data("Tata Tea Gold 1kg")
    assert groceries.category == "groceries"
    groceries_rets = {l.retailer_name for l in groceries.variants[0].listings}
    assert {"Amazon India", "Flipkart", "Meesho"}.issubset(groceries_rets)

    # 5. Books
    books = scraper.generate_product_data("Atomic Habits by James Clear")
    assert books.category == "books"
    books_rets = {l.retailer_name for l in books.variants[0].listings}
    assert {"Amazon India", "Flipkart", "Meesho"}.issubset(books_rets)


def test_gbm_enriched_feature_accuracy():
    """Test that GBMPointForecaster trains and forecasts accurately with enriched features."""
    np.random.seed(42)
    t = np.arange(180)
    trend = 50000 - 15 * t
    seasonality = 400 * np.sin(2 * np.pi * t / 7)
    noise = np.random.normal(0, 50, size=180)
    y = trend + seasonality + noise

    forecaster = GBMPointForecaster(max_horizon=30)
    horizons = fit_horizons(30)
    forecaster.fit(y, horizons)

    quantiles = [0.10, 0.25, 0.50, 0.75, 0.90]
    forecast = forecaster.forecast_quantiles(y, horizon=7, quantiles=quantiles)

    assert forecast.shape == (7, 5)
    for row in forecast:
        assert row[0] <= row[1] <= row[2] <= row[3] <= row[4]
    
    last_price = y[-1]
    assert abs(forecast[0, 2] - last_price) < 2000.0


def test_prediction_engine_cached_subsecond_inference():
    """Verify prediction engine produces calibrated forecast and caches backtest for zero-delay response."""
    engine = PredictionEngine(registry_dir="ml/model_registry")
    
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=90, freq="D")
    prices = 25000 + np.cumsum(np.random.normal(0, 30, size=90))
    series = pd.Series(prices, index=dates)

    res1 = engine.forecast_from_series(series, horizon=7)
    assert res1.quantiles.shape == (7, 7)
    assert res1.confidence["score"] > 0.0

    start = datetime.now()
    res2 = engine.forecast_from_series(series, horizon=7)
    elapsed = (datetime.now() - start).total_seconds()
    
    assert elapsed < 1.0  # Sub-second execution
    np.testing.assert_allclose(res1.quantiles, res2.quantiles)


@pytest.mark.asyncio
async def test_universal_scrape_and_ingest_db():
    """Verify universal_scraper.scrape_and_ingest writes products, variants, listings, and observations into DB."""
    from database.session import create_engine, create_session_factory, init_db
    test_engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_db(test_engine)
    factory = create_session_factory(test_engine)
    async with factory() as db:
        products = await universal_scraper.scrape_and_ingest(db, "Levi's 511 Slim Jeans")
        assert len(products) >= 1
        p = products[0]
        assert "Levi" in p.canonical_name
        assert len(p.variants) >= 2
        v = p.variants[0]
        retailers = {l.retailer.name if l.retailer else "" for l in v.listings}
        assert len(v.listings) >= 3
    await test_engine.dispose()
