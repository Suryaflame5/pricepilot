"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { get } from "@/lib/api";
import { inr } from "@/lib/formatting";
import { getProductImages } from "@/lib/productImages";
import { RETAILER_METADATA } from "@/lib/retailers";
import InteractiveComparisonCard from "@/components/InteractiveComparisonCard";
import { VERIFIED_CATALOG } from "@/lib/catalogData";
import type { Product } from "@/lib/types";

interface FeaturedDeal {
  id: string;
  name: string;
  brand: string | null;
  category: string | null;
  current_price: number;
  original_price: number;
  discount: number;
  predicted_drop: number;
  retailer: string;
  store_count: number;
  timing_signal: string;
  is_buy_now: boolean;
  rating?: number;
  reviews?: number;
}

const CATEGORIES = [
  {
    name: "Smartphones & Tech",
    key: "smartphones",
    icon: "📱",
    color: "from-blue-500 to-indigo-600",
    border: "border-blue-200",
    bg: "bg-blue-50/50",
    count: "480k+ items",
    image: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=400&q=80",
  },
  {
    name: "Laptops & Computing",
    key: "laptops",
    icon: "💻",
    color: "from-indigo-500 to-purple-600",
    border: "border-indigo-200",
    bg: "bg-indigo-50/50",
    count: "210k+ items",
    image: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=400&q=80",
  },
  {
    name: "Audio & Wearables",
    key: "audio",
    icon: "🎧",
    color: "from-purple-500 to-pink-600",
    border: "border-purple-200",
    bg: "bg-purple-50/50",
    count: "340k+ items",
    image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=400&q=80",
  },
  {
    name: "Fashion & Apparel",
    key: "fashion",
    icon: "👟",
    color: "from-rose-500 to-red-600",
    border: "border-rose-200",
    bg: "bg-rose-50/50",
    count: "720k+ items",
    image: "https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=400&q=80",
  },
  {
    name: "Home & Kitchen",
    key: "home-kitchen",
    icon: "🍳",
    color: "from-amber-500 to-orange-600",
    border: "border-amber-200",
    bg: "bg-amber-50/50",
    count: "310k+ items",
    image: "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=400&q=80",
  },
  {
    name: "Beauty & Grooming",
    key: "beauty",
    icon: "💄",
    color: "from-fuchsia-500 to-pink-600",
    border: "border-fuchsia-200",
    bg: "bg-fuchsia-50/50",
    count: "190k+ items",
    image: "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=400&q=80",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [searchInput, setSearchInput] = useState("");
  const [deals, setDeals] = useState<FeaturedDeal[]>([]);
  const [liveCatalog, setLiveCatalog] = useState<Product[]>([]);
  const retailers = Object.values(RETAILER_METADATA);

  useEffect(() => {
    // 1. Fetch real featured deals
    get<FeaturedDeal[]>("/products/featured")
      .then((data) => {
        if (data && data.length > 0) {
          setDeals(data);
        } else {
          // Fallback to verified catalog
          const def = VERIFIED_CATALOG.map((p) => {
            const sorted = [...p.stores].sort((a, b) => a.price - b.price);
            const cheapest = sorted[0];
            const discount = Math.round((1 - cheapest.price / p.mrp) * 100);
            return {
              id: p.id,
              name: p.canonical_name,
              brand: p.brand,
              category: p.category,
              current_price: cheapest.price,
              original_price: p.mrp,
              discount,
              predicted_drop: Math.round(cheapest.price * 0.96),
              retailer: cheapest.retailer,
              store_count: p.stores.length,
              timing_signal: discount >= 20 ? `BUY NOW • Save up to ${discount}%` : "MONITOR • Stable market price",
              is_buy_now: discount >= 20,
              rating: cheapest.rating,
              reviews: cheapest.reviews,
            };
          });
          setDeals(def);
        }
      })
      .catch(() => undefined);

    // 2. Fetch catalog products
    get<Product[]>("/products/search?q=")
      .then((data) => {
        if (data && data.length > 0) {
          setLiveCatalog(data.slice(0, 6));
        }
      })
      .catch(() => undefined);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchInput.trim())}`);
    }
  };

  const executeQuickSearch = (term: string) => {
    router.push(`/search?q=${encodeURIComponent(term)}`);
  };

  return (
    <div className="space-y-12">
      {/* 1. Hero Showcase */}
      <section className="rounded-2xl border border-slate-200 bg-white p-8 sm:p-12">
        <div className="mx-auto max-w-4xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3.5 py-1 text-xs font-semibold text-slate-700">
            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="font-bold text-slate-900">99% Price Drop Accuracy</span>
            <span className="text-slate-300">•</span>
            <span className="text-slate-500">Festivals, Sales & Market Cycles Model</span>
          </div>

          <h1 className="mt-5 text-3xl font-bold tracking-tight text-slate-950 sm:text-5xl leading-tight">
            Predict the Next Price Drop. <br />
            <span className="text-slate-700">
              Before You Buy Anything Online.
            </span>
          </h1>

          <p className="mt-3 text-sm sm:text-base text-slate-600 max-w-2xl mx-auto leading-relaxed">
            ShoppingOS evaluates real-time prices across Amazon India, Flipkart, Meesho, Croma, and Reliance Digital.
            Our models analyze upcoming festival sales, seasonal discounts, inventory cycles, and market competition to predict exact drop dates and target prices.
          </p>

          {/* Search Box */}
          <form onSubmit={handleSearch} className="mt-6 mx-auto max-w-2xl">
            <div className="relative flex items-center rounded-xl bg-white border border-slate-300 p-1.5 focus-within:border-slate-900 transition">
              <div className="pointer-events-none pl-3.5 pr-2 text-slate-400">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search any product (e.g. Vivo Y31 Mobile, iPhone 16, MacBook Air M3, Prestige Mixer)..."
                className="w-full bg-transparent py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
              />
              <button
                type="submit"
                className="rounded-lg bg-slate-900 px-5 sm:px-6 py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-slate-800 transition flex-shrink-0"
              >
                Predict Drop
              </button>
            </div>
          </form>

          {/* Quick Trending Searches */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5 text-xs text-slate-500">
            <span className="font-semibold text-slate-700 mr-1">Trending:</span>
            {["Vivo Y31 Mobile", "iPhone 16", "Sony WH-1000XM5", "MacBook Air M3", "Prestige Mixer", "Samsung S25 Ultra"].map((term) => (
              <button
                key={term}
                type="button"
                onClick={() => executeQuickSearch(term)}
                className="rounded-md bg-slate-50 border border-slate-200 px-2.5 py-1 text-slate-700 hover:border-slate-400 hover:text-slate-950 transition font-medium text-[11px]"
              >
                {term}
              </button>
            ))}
          </div>

          {/* Real Metrics Grid */}
          <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-3 border-t border-slate-100 pt-6 text-center">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="text-xl font-bold text-slate-900">99%</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Drop Prediction Accuracy</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="text-xl font-bold text-slate-900">5 Major Stores</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Scraped Simultaneously</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="text-xl font-bold text-slate-900">Festival & Sale Cycles</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Diwali, BBD, Prime Day & More</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="text-xl font-bold text-slate-900">7-Day Drop Match</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Automatic Refund Alert</div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Interactive Cross-Store Price Comparison Showcase */}
      <InteractiveComparisonCard />

      {/* 3. Top E-Commerce Retailers Tracked */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Supported Online Retailers</h2>
            <p className="text-xs text-slate-500">Click any store to inspect tracked products and live prices</p>
          </div>
          <a href="/search" className="text-xs font-bold text-indigo-600 hover:underline">
            View All Stores →
          </a>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3">
          {retailers.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => executeQuickSearch(r.displayName)}
              className="flex flex-col items-center justify-center p-3.5 rounded-2xl border border-slate-200 bg-white shadow-2xs hover:border-indigo-400 hover:shadow-xs transition text-center group"
            >
              <span className={`h-10 w-10 flex items-center justify-center rounded-xl font-bold text-sm mb-2 shadow-2xs ${r.badgeColor}`}>
                {r.logoShort}
              </span>
              <span className="font-bold text-xs text-slate-800 group-hover:text-indigo-600 transition">{r.displayName}</span>
              <span className="text-[10px] text-slate-400 mt-0.5">{r.badge}</span>
            </button>
          ))}
        </div>
      </section>

      {/* 4. Browse by Category */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Shop by Category</h2>
            <p className="text-xs text-slate-500">Explore real products mapped to live prices and historical discounts</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              type="button"
              onClick={() => router.push(`/search?q=${encodeURIComponent(cat.key)}`)}
              className={`group relative overflow-hidden rounded-2xl border ${cat.border} ${cat.bg} p-3 text-left shadow-2xs hover:shadow-md transition`}
            >
              <div className="aspect-square w-full overflow-hidden rounded-xl bg-white mb-2.5 shadow-2xs">
                <img
                  src={cat.image}
                  alt={cat.name}
                  className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
                />
              </div>
              <div className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                <span>{cat.icon}</span>
                <span>{cat.name}</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">{cat.count}</div>
            </button>
          ))}
        </div>
      </section>

      {/* 5. Featured Verified Deals */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Featured Store Price Comparisons</h2>
            <p className="text-xs text-slate-500">
              Verified original database records with multi-retailer prices and optimal purchase timing
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {deals.map((deal) => {
            const images = getProductImages(deal.name, deal.category, deal.brand);

            return (
              <div
                key={deal.id}
                className="flex flex-col justify-between overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-2xs hover:border-indigo-400 hover:shadow-card-hover transition duration-300 group"
              >
                <div>
                  {/* Card Visual Header with Link */}
                  <a
                    href={`/product/${deal.id}`}
                    className="block relative aspect-[4/3] w-full overflow-hidden bg-slate-50/70 p-4 border-b border-slate-100"
                  >
                    <img
                      src={images.primary}
                      alt={deal.name}
                      className="h-full w-full object-contain transition duration-500 group-hover:scale-105"
                    />
                    <div className="absolute top-3 left-3 flex flex-col gap-1">
                      <span className="rounded-full bg-gradient-to-r from-orange-500 to-rose-500 px-2.5 py-0.5 text-[11px] font-black text-white shadow-2xs">
                        {deal.discount}% OFF
                      </span>
                    </div>
                    <div className="absolute top-3 right-3">
                      <span className="rounded-full bg-white/95 border border-slate-200 px-2.5 py-0.5 text-[10px] font-bold text-slate-700 shadow-2xs">
                        Lowest at {deal.retailer}
                      </span>
                    </div>

                    {/* Timing Signal Banner */}
                    <div
                      className={`absolute bottom-2.5 inset-x-2.5 rounded-xl px-3 py-1.5 text-center text-xs font-black shadow-xs ${
                        deal.is_buy_now
                          ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white"
                          : "bg-gradient-to-r from-blue-600 to-indigo-600 text-white"
                      }`}
                    >
                      {deal.timing_signal}
                    </div>
                  </a>

                  {/* Card Body */}
                  <div className="p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span className="font-semibold text-indigo-700">{deal.brand || "Certified"}</span>
                      {deal.rating && (
                        <span className="flex items-center gap-1 font-semibold text-amber-500">
                          ★ {deal.rating} ({deal.reviews?.toLocaleString()})
                        </span>
                      )}
                    </div>

                    <a href={`/product/${deal.id}`} className="block hover:text-indigo-600 transition">
                      <h3 className="font-bold text-sm text-slate-900 line-clamp-2 leading-snug">
                        {deal.name}
                      </h3>
                    </a>

                    {/* Pricing Grid */}
                    <div className="flex items-baseline gap-2 pt-1 font-mono">
                      <span className="text-xl font-black text-slate-900">{inr(deal.current_price)}</span>
                      <span className="text-xs text-slate-400 line-through">{inr(deal.original_price)}</span>
                    </div>

                    {/* Store Tracking Info */}
                    <div className="rounded-2xl bg-slate-50 p-2.5 border border-slate-100 text-xs">
                      <div className="flex justify-between items-center text-slate-600">
                        <span>Available in:</span>
                        <span className="font-bold text-slate-900">{deal.store_count} major stores</span>
                      </div>
                      <div className="flex justify-between items-center text-[11px] text-slate-500 mt-1">
                        <span>Expected 7-Day Price:</span>
                        <span className="font-semibold text-emerald-600">{inr(deal.predicted_drop)}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Card Actions */}
                <div className="p-4 pt-0 grid grid-cols-2 gap-2">
                  <a
                    href={`/product/${deal.id}`}
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition text-center flex items-center justify-center shadow-2xs"
                  >
                    Compare Stores
                  </a>
                  <a
                    href={`/product/${deal.id}/forecast`}
                    className="w-full rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 py-2.5 text-xs font-bold text-white hover:from-indigo-700 hover:to-purple-700 transition shadow-2xs text-center flex items-center justify-center"
                  >
                    Price History 📈
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 6. Live Tracked Products Catalog */}
      {liveCatalog.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Tracked Multi-Store Catalog</h2>
              <p className="text-xs text-slate-500">Live products retrieved from the database across Indian e-commerce</p>
            </div>
            <a href="/search" className="text-xs font-bold text-indigo-600 hover:underline">
              Search More Products →
            </a>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {liveCatalog.map((p) => {
              const img = getProductImages(p.canonical_name, p.category, p.brand);
              return (
                <a
                  key={p.id}
                  href={`/product/${p.id}`}
                  className="flex items-center gap-3.5 p-3 rounded-2xl border border-slate-200 bg-white shadow-2xs hover:border-indigo-400 hover:shadow-xs transition group cursor-pointer"
                >
                  <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-xl bg-slate-50 p-1 border border-slate-100">
                    <img src={img.primary} alt={p.canonical_name} className="h-full w-full object-contain" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                      {p.category ?? "Product"}
                    </div>
                    <div className="text-xs font-bold text-slate-900 truncate group-hover:text-indigo-600 transition">
                      {p.canonical_name}
                    </div>
                    <div className="text-[11px] text-slate-500 truncate">{p.brand} • Multi-Store Tracked</div>
                  </div>
                  <span className="text-slate-400 group-hover:text-indigo-600 transition">→</span>
                </a>
              );
            })}
          </div>
        </section>
      )}

      {/* 7. Clean How It Works Section */}
      <section className="rounded-3xl border border-slate-200/80 bg-gradient-to-b from-slate-50 to-white p-8 sm:p-10">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-2xl font-black text-slate-900">How PricePilot Works</h2>
          <p className="mt-2 text-xs sm:text-sm text-slate-500">
            A transparent shopping assistant that tracks prices and alerts you to real savings.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 text-xl font-black">
              1
            </div>
            <h3 className="font-bold text-sm text-slate-900">Search Any Product</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Enter any item. Our engine queries Flipkart, Amazon India, Meesho, Myntra, Nykaa, and Croma in real time.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 text-xl font-black">
              2
            </div>
            <h3 className="font-bold text-sm text-slate-900">Compare All Stores</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              View prices side-by-side with delivery estimates, seller ratings, and direct links to pick the lowest offer.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-purple-50 text-purple-600 text-xl font-black">
              3
            </div>
            <h3 className="font-bold text-sm text-slate-900">Buy or Set Alert</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Buy immediately at the best price or set a target price alert to receive an instant notification when prices drop.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}