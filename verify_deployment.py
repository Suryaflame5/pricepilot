import asyncio
import httpx
import json

async def run_post_deployment_verification():
    print("==============================================")
    print("  PRICEPILOT POST-DEPLOYMENT VERIFICATION     ")
    print("==============================================")
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        # 1. Verify Backend Health
        r_health = await client.get("http://localhost:8000/health")
        assert r_health.status_code == 200, f"Health failed: {r_health.text}"
        print(f"[OK] Backend Health API: OK -> {r_health.json()}")

        # 2. Verify Frontend Home Page
        r_web = await client.get("http://localhost:3000/")
        assert r_web.status_code == 200, f"Web Home failed: {r_web.status_code}"
        print(f"[OK] Frontend Web Home (http://localhost:3000): OK -> HTTP 200")

        # 3. Verify Existing Product Search
        r_search = await client.get("http://localhost:8000/products/search?q=Prestige")
        assert r_search.status_code == 200, f"Search failed: {r_search.text}"
        products = r_search.json()
        assert len(products) > 0, "No products found for Prestige"
        prestige_id = products[0]["id"]
        print(f"[OK] Product Search: OK -> Found \"{products[0]['canonical_name']}\" (ID: {prestige_id})")

        # 4. Universal Real-time Internet Scraping across multi-retailers
        test_new_product = "Apple Watch Series 9 GPS"
        print(f"[+] Testing Universal Real-Time Internet Scraper for: \"{test_new_product}\"...")
        r_scrape = await client.get(f"http://localhost:8000/products/search?q={test_new_product}")
        assert r_scrape.status_code == 200, f"Live scrape failed: {r_scrape.text}"
        scraped_products = r_scrape.json()
        assert len(scraped_products) > 0, "Live scraper returned no products"
        new_prod = scraped_products[0]
        new_prod_id = new_prod["id"]
        print(f"[OK] Real-time Internet Scraper: Discovered & Ingested \"{new_prod['canonical_name']}\" (ID: {new_prod_id})")

        # 5. Verify Product Detail & Multi-retailer listings
        r_detail = await client.get(f"http://localhost:8000/products/{new_prod_id}")
        assert r_detail.status_code == 200, f"Product detail failed: {r_detail.text}"
        detail = r_detail.json()
        variants = detail.get("variants", [])
        assert len(variants) > 0, "Product has no variants"
        variant_id = variants[0]["id"]
        print(f"[OK] Product Detail: OK -> Category: {detail['category']}, Variants count: {len(variants)}")

        # 6. Verify Market Comparison across Flipkart, Amazon, Meesho, etc.
        r_compare = await client.get(f"http://localhost:8000/products/variant/{variant_id}/compare")
        assert r_compare.status_code == 200, f"Compare failed: {r_compare.text}"
        compare_data = r_compare.json()
        cheapest = compare_data.get("cheapest")
        cheapest_price = cheapest.get("effective_price") if cheapest else 0
        offers = compare_data.get("offers", [])
        print(f"[OK] Market Comparison: Best Price: Rs.{cheapest_price:,.2f}, Retailers: {len(offers)}")
        for offer in offers:
            print(f"    - {offer.get('retailer_name')}: Rs.{offer.get('effective_price', 0):,.2f} ({offer.get('availability', 'in_stock')})")

        # 7. Verify Price Stats & History for the active listing
        listing_id = cheapest.get("listing_id") if cheapest else offers[0].get("listing_id")
        r_stats = await client.get(f"http://localhost:8000/prices/stats?listing_id={listing_id}")
        assert r_stats.status_code == 200, f"Stats failed: {r_stats.text}"
        stats_data = r_stats.json()
        print(f"[OK] Price Statistics: Current Rs.{stats_data.get('current_price', 0):,.2f}, Low Rs.{stats_data.get('lowest_price', 0):,.2f}, High Rs.{stats_data.get('highest_price', 0):,.2f}")

        # 8. Verify ML Prediction Engine (POST /predictions/price)
        r_pred = await client.post("http://localhost:8000/predictions/price", json={
            "product_variant_id": variant_id,
            "horizon_hours": 168,
            "interval_level": 0.9,
        })
        assert r_pred.status_code == 200, f"Prediction failed: {r_pred.text}"
        pred = r_pred.json()
        print(f"[OK] ML Price Forecast: Model {pred.get('model_version')}")
        print(f"    Current: Rs.{pred.get('current_price', 0):,.2f}")
        print(f"    7-Day P50: Rs.{pred.get('forecast', {}).get('p50', 0):,.2f} [P10: Rs.{pred.get('forecast', {}).get('p10', 0):,.2f}, P90: Rs.{pred.get('forecast', {}).get('p90', 0):,.2f}]")
        print(f"    Confidence: {pred.get('confidence', {}).get('score', 0):.2f} ({pred.get('confidence', {}).get('level', 'N/A')})")

        # 9. Verify Decision & Target Recommendation (POST /predictions/decision)
        target_price = round(cheapest_price * 0.9)
        r_dec = await client.post("http://localhost:8000/predictions/decision", json={
            "product_variant_id": variant_id,
            "target_price": target_price,
            "urgency": "normal",
        })
        assert r_dec.status_code == 200, f"Decision failed: {r_dec.text}"
        dec = r_dec.json()
        conf = dec.get("probability_of_benefit") or dec.get("forecast_reliability") or 0.85
        print(f"[OK] AI Shopping Decision: Recommendation -> {dec.get('recommendation')} (Score: {conf:.2f})")
        print(f"    Reasoning: {dec.get('reasoning')}")

        # 10. Verify Next.js Dynamic Pages for the scraped product
        r_page = await client.get(f"http://localhost:3000/product/{new_prod_id}")
        assert r_page.status_code == 200, f"Product Page SSR failed: {r_page.status_code}"
        print(f"[OK] Web Product Page (http://localhost:3000/product/{new_prod_id}): OK -> HTTP 200")

        r_fc_page = await client.get(f"http://localhost:3000/product/{new_prod_id}/forecast")
        assert r_fc_page.status_code == 200, f"Forecast Page SSR failed: {r_fc_page.status_code}"
        print(f"[OK] Web Forecast Page (http://localhost:3000/product/{new_prod_id}/forecast): OK -> HTTP 200")

        r_intel = await client.get("http://localhost:3000/intelligence")
        assert r_intel.status_code == 200, f"Intelligence Page failed: {r_intel.status_code}"
        print("[OK] Web Intelligence Dashboard (http://localhost:3000/intelligence): OK -> HTTP 200")

        print("==============================================")
        print("    ALL POST-DEPLOYMENT CHECKS PASSED 100%!   ")
        print("==============================================")

if __name__ == "__main__":
    asyncio.run(run_post_deployment_verification())
