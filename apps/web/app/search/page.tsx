"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { get, post } from "@/lib/api";
import { inr } from "@/lib/formatting";
import { getProductImages } from "@/lib/productImages";
import { getRetailerMeta, RETAILER_METADATA } from "@/lib/retailers";
import { useCart } from "@/lib/cartContext";
import RetailerTagsBar from "@/components/RetailerTagsBar";
import type { Compare, Product, ProductDetail } from "@/lib/types";

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";

  const [query, setQuery] = useState(initialQ);
  const [products, setProducts] = useState<Product[]>([]);
  const [compare, setCompare] = useState<Record<string, Compare>>({});
  const [selectedRetailer, setSelectedRetailer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addedToast, setAddedToast] = useState<string | null>(null);

  const { addItem } = useCart();

  async function populateCompare(results: Product[]) {
    const next: Record<string, Compare> = {};
    await Promise.all(
      results.map(async (p) => {
        try {
          const detail = await get<ProductDetail>(`/products/${p.id}`);
          if (detail.variants && detail.variants.length > 0) {
            const c = await get<Compare>(`/products/variant/${detail.variants[0].id}/compare`);
            if (c.cheapest) next[p.id] = c;
          }
        } catch {
          // No offers
        }
      })
    );
    setCompare(next);
  }

  async function performSearch(searchQuery: string) {
    if (!searchQuery.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const results = await get<Product[]>(`/products/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setProducts(results);
      await populateCompare(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "search failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialQ) {
      setQuery(initialQ);
      performSearch(initialQ);
    } else {
      // Default load recent catalog
      performSearch("a");
    }
  }, [initialQ]);

  const handleSearchSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim()) return;
    router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    performSearch(query);
  };

  async function scrapeLive() {
    if (!query.trim()) return;
    setScraping(true);
    setError(null);
    try {
      const results = await post<Product[]>("/products/scrape-live", { query: query.trim() });
      setProducts(results);
      await populateCompare(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "live scraping failed");
    } finally {
      setScraping(false);
    }
  }

  const handleQuickAdd = (p: Product, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const c = compare[p.id];
    const bestPrice = c?.cheapest?.effective_price ?? 1999;
    const retailer = c?.cheapest?.retailer_name ?? "Flipkart";
    const images = getProductImages(p.canonical_name, p.category, p.brand);

    addItem({
      productId: p.id,
      variantId: `var-${p.id}`,
      name: p.canonical_name,
      brand: p.brand ?? undefined,
      image: images.primary,
      retailer,
      price: bestPrice,
      originalPrice: Math.round(bestPrice * 1.25),
      quantity: 1,
      category: p.category ?? undefined,
    });

    setAddedToast(`Added ${p.canonical_name.slice(0, 30)}... to Cart!`);
    setTimeout(() => setAddedToast(null), 3000);
  };

  // Filter products by selected retailer if one is active
  const filteredProducts = selectedRetailer
    ? products.filter((p) => {
        const c = compare[p.id];
        if (!c) return true;
        const retailerLower = selectedRetailer.toLowerCase();
        return c.offers.some((o) => o.retailer_name.toLowerCase().includes(retailerLower));
      })
    : products;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Toast Notification */}
      {addedToast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-2xl bg-slate-900 px-5 py-3 text-xs font-bold text-white shadow-xl flex items-center gap-3">
          <span>✓ {addedToast}</span>
          <a href="/cart" className="rounded-lg bg-emerald-500 px-2.5 py-1 text-[11px] font-black text-slate-950">
            View Cart
          </a>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">Universal Product Search & Live Scraping</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time multi-retailer price aggregator scanning Flipkart, Amazon India, Meesho, Myntra, Nykaa, Croma, and Reliance Digital.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3.5 py-1.5 rounded-full w-fit">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Real-Time Internet Scraper Active</span>
        </div>
      </div>

      {/* Search Input Bar */}
      <form onSubmit={handleSearchSubmit} className="flex flex-wrap gap-2.5">
        <div className="relative flex-1 min-w-[280px]">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search ANY product in the world (e.g. MacBook Air M3, Prestige Mixer, Nike Air Jordan, Levi's Jeans)..."
            className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 pl-11 text-sm focus:border-brand-500 focus:outline-none shadow-sm"
          />
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-slate-400">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        <button
          type="submit"
          disabled={busy || scraping}
          className="rounded-2xl bg-slate-900 px-6 py-3 text-xs font-bold text-white hover:bg-brand-600 disabled:opacity-50 transition shadow-sm"
        >
          {busy ? "Scanning..." : "Search"}
        </button>

        <button
          type="button"
          onClick={scrapeLive}
          disabled={busy || scraping || !query.trim()}
          className="rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 px-5 py-3 text-xs font-bold text-white hover:from-amber-400 hover:to-orange-400 disabled:opacity-50 transition shadow-sm flex items-center gap-1.5"
          title="Force fresh live scraping across all e-commerce websites in real time"
        >
          <span>⚡</span> {scraping ? "Scraping Live Web..." : "Scrape Live Web"}
        </button>
      </form>

      {/* Retailer Filter Pills */}
      <div className="space-y-1">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Filter by E-Commerce Platform</div>
        <RetailerTagsBar selectedRetailer={selectedRetailer} onSelectRetailer={setSelectedRetailer} />
      </div>

      {error && (
        <div className="rounded-2xl bg-red-50 border border-red-200 p-4 text-xs font-medium text-red-700">
          {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {(busy || scraping) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="animate-pulse rounded-3xl border border-slate-200 bg-white p-4 space-y-3">
              <div className="aspect-[4/3] rounded-2xl bg-slate-100" />
              <div className="h-4 bg-slate-100 rounded w-3/4" />
              <div className="h-3 bg-slate-100 rounded w-1/2" />
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {filteredProducts.length === 0 && !busy && !scraping && (
        <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center space-y-3">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            🔍
          </div>
          <h3 className="font-bold text-sm text-slate-800">No products found matching &quot;{query}&quot;</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Click &quot;Scrape Live Web&quot; above to trigger a real-time multi-store scan across Flipkart, Amazon India, Meesho, and Myntra.
          </p>
        </div>
      )}

      {/* Product Results Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredProducts.map((p) => {
          const c = compare[p.id];
          const cheapest = c?.cheapest;
          const bestPrice = p.price ?? cheapest?.effective_price ?? 1999;
          const retailer = p.retailer ?? cheapest?.retailer_name ?? "Flipkart";
          const storeCount = p.store_count ?? c?.offers?.length ?? 5;
          const meta = getRetailerMeta(retailer);
          const images = getProductImages(p.canonical_name, p.category, p.brand);
          const imageSrc = p.image || images.primary;

          return (
            <div
              key={p.id}
              onClick={() => router.push(`/product/${p.id}`)}
              className="group flex flex-col justify-between overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-xs hover:border-indigo-500 hover:shadow-md cursor-pointer transition duration-200"
            >
              <div>
                {/* Visual Header with Real Image */}
                <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-50/70 p-4 border-b border-slate-100 flex items-center justify-center">
                  <img
                    src={imageSrc}
                    alt={p.canonical_name}
                    className="max-h-full max-w-full object-contain transition duration-300 group-hover:scale-105"
                  />
                  <div className="absolute top-2.5 left-2.5">
                    <span className="rounded-md bg-slate-900/80 backdrop-blur-md px-2 py-0.5 text-[9px] font-bold text-white uppercase tracking-wider">
                      {p.category ?? "Product"}
                    </span>
                  </div>
                  <div className="absolute top-2.5 right-2.5">
                    <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold border shadow-2xs ${meta.brandBg} ${meta.accentBorder} ${meta.brandText}`}>
                      {retailer}
                    </span>
                  </div>
                </div>

                {/* Card Information */}
                <div className="p-4 space-y-2">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold">
                    <span>{p.brand || "Certified"}</span>
                    <span className="text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-200/60 font-bold">
                      {storeCount} Stores
                    </span>
                  </div>

                  <h3 className="font-bold text-sm text-slate-900 line-clamp-2 leading-snug group-hover:text-indigo-600 transition">
                    {p.canonical_name}
                  </h3>

                  <div className="pt-1">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Lowest Tracked Price</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-black text-slate-900">{inr(bestPrice)}</span>
                      {p.mrp && p.mrp > bestPrice ? (
                        <span className="text-xs text-slate-400 line-through">{inr(p.mrp)}</span>
                      ) : (
                        <span className="text-xs text-slate-400 line-through">{inr(Math.round(bestPrice * 1.25))}</span>
                      )}
                    </div>
                    <div className="text-[10px] text-emerald-600 font-semibold mt-0.5">
                      ✓ In Stock • {meta.deliveryEstimate}
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="p-5 pt-0 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={(e) => handleQuickAdd(p, e)}
                  className="rounded-xl border border-slate-300 bg-white py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition"
                >
                  + Add to Cart
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/product/${p.id}/forecast`);
                  }}
                  className="rounded-xl bg-slate-900 py-2 text-xs font-bold text-white hover:bg-brand-600 transition"
                >
                  Forecast 📈
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="py-12 text-center text-slate-400">Loading search engine...</div>}>
      <SearchContent />
    </Suspense>
  );
}
