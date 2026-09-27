"use client";

import { useState } from "react";
import { inr } from "@/lib/formatting";
import { getProductImages } from "@/lib/productImages";
import { VERIFIED_CATALOG, type CatalogProduct } from "@/lib/catalogData";

export default function InteractiveComparisonCard() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const activeProduct = VERIFIED_CATALOG[selectedIdx];

  const sortedStores = [...activeProduct.stores].sort((a, b) => a.price - b.price);
  const cheapest = sortedStores[0];
  const mostExpensive = sortedStores[sortedStores.length - 1];
  const maxSavings = mostExpensive.price - cheapest.price;
  const images = getProductImages(activeProduct.canonical_name, activeProduct.category, activeProduct.brand);

  const getRetailerBadge = (name: string) => {
    switch (name.toLowerCase()) {
      case "amazon india":
        return "bg-amber-100 text-amber-900 border-amber-300";
      case "flipkart":
        return "bg-blue-100 text-blue-900 border-blue-300";
      case "meesho":
        return "bg-pink-100 text-pink-900 border-pink-300";
      case "myntra":
        return "bg-rose-100 text-rose-900 border-rose-300";
      case "nykaa":
        return "bg-fuchsia-100 text-fuchsia-900 border-fuchsia-300";
      case "croma":
        return "bg-teal-100 text-teal-900 border-teal-300";
      case "reliance digital":
        return "bg-red-100 text-red-900 border-red-300";
      default:
        return "bg-slate-100 text-slate-800 border-slate-300";
    }
  };

  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white p-6 sm:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-100 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 border border-emerald-200">
            <span>⚡ Live Cross-Store Price Spread</span>
          </div>
          <h2 className="mt-2 text-xl sm:text-2xl font-black text-slate-900">
            See the exact price difference between stores
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Prices for the identical genuine product vary by thousands of rupees across platforms.
          </p>
        </div>

        {/* Product Switcher Pills */}
        <div className="flex flex-wrap gap-1.5 max-w-md">
          {VERIFIED_CATALOG.slice(0, 5).map((p, idx) => (
            <button
              key={p.id}
              onClick={() => setSelectedIdx(idx)}
              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                selectedIdx === idx
                  ? "bg-slate-900 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {p.canonical_name.split(" ")[0]} {p.canonical_name.split(" ")[1]}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Left: Product Visual & Highlight */}
        <div className="lg:col-span-4 flex flex-col items-center text-center p-4 rounded-2xl bg-slate-50 border border-slate-100">
          <div className="h-44 w-44 overflow-hidden rounded-2xl bg-white p-3 shadow-2xs">
            <img
              src={images.primary}
              alt={activeProduct.canonical_name}
              className="h-full w-full object-contain transition duration-300 hover:scale-105"
            />
          </div>
          <div className="mt-3 font-bold text-xs uppercase tracking-wider text-indigo-600">
            {activeProduct.brand} • {activeProduct.category}
          </div>
          <h3 className="mt-1 font-bold text-sm text-slate-900 line-clamp-2">
            {activeProduct.canonical_name}
          </h3>

          <div className="mt-4 w-full rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 p-3.5 text-white shadow-md shadow-emerald-500/20">
            <div className="text-[11px] font-bold text-emerald-100 uppercase tracking-wider">
              Maximum Savings Today
            </div>
            <div className="text-2xl font-black mt-0.5">{inr(maxSavings)}</div>
            <div className="text-[11px] text-emerald-100 mt-1">
              Cheapest on <strong>{cheapest.retailer}</strong> vs {mostExpensive.retailer}
            </div>
          </div>
        </div>

        {/* Right: Comparative Store Bars */}
        <div className="lg:col-span-8 space-y-3.5">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Live Store Offers (Lowest to Highest)
          </div>

          {sortedStores.map((store, idx) => {
            const isLowest = idx === 0;
            const diffFromLowest = store.price - cheapest.price;
            const percentWidth = Math.max(30, Math.round((store.price / activeProduct.mrp) * 100));

            return (
              <div
                key={store.retailer}
                className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-2xl border transition ${
                  isLowest
                    ? "border-emerald-300 bg-emerald-50/40 shadow-xs ring-1 ring-emerald-500/20"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-3 min-w-[160px]">
                  <span
                    className={`rounded-xl px-2.5 py-1 text-xs font-bold border ${getRetailerBadge(
                      store.retailer
                    )}`}
                  >
                    {store.retailer}
                  </span>
                  {isLowest && (
                    <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-black text-white uppercase tracking-wider">
                      Best Deal
                    </span>
                  )}
                </div>

                {/* Comparative Price Gauge */}
                <div className="flex-1 max-w-xs">
                  <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        isLowest
                          ? "bg-gradient-to-r from-emerald-500 to-teal-500"
                          : "bg-slate-400"
                      }`}
                      style={{ width: `${percentWidth}%` }}
                    />
                  </div>
                  <div className="flex justify-between items-center text-[10px] text-slate-400 mt-1">
                    <span>Est. {store.delivery}</span>
                    <span>★ {store.rating} ({store.reviews.toLocaleString()} reviews)</span>
                  </div>
                </div>

                <div className="flex items-center justify-between sm:justify-end gap-3 text-right">
                  <div>
                    <div className="text-base font-black text-slate-900">{inr(store.price)}</div>
                    {diffFromLowest > 0 ? (
                      <div className="text-[10px] font-semibold text-rose-500">
                        +{inr(diffFromLowest)} higher
                      </div>
                    ) : (
                      <div className="text-[10px] font-bold text-emerald-600">
                        Lowest price
                      </div>
                    )}
                  </div>

                  <a
                    href={`/product/${activeProduct.id}`}
                    className={`rounded-xl px-3.5 py-2 text-xs font-bold transition shadow-2xs ${
                      isLowest
                        ? "bg-emerald-600 text-white hover:bg-emerald-700"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    View Offer
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
