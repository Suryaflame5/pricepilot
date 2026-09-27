"use client";

import { inr } from "@/lib/formatting";
import { getRetailerMeta } from "@/lib/retailers";
import type { RetailerOffer } from "@/lib/types";

interface Props {
  offers: RetailerOffer[];
  productName: string;
}

export default function ArbitrageSpreadMatrix({ offers, productName }: Props) {
  if (!offers || offers.length === 0) return null;

  // Sort offers by effective price ascending
  const sorted = [...offers].sort((a, b) => (a.effective_price ?? 999999) - (b.effective_price ?? 999999));
  const cheapest = sorted[0];
  const mostExpensive = sorted[sorted.length - 1];
  const maxPrice = mostExpensive.effective_price ?? 1;
  const maxSavings = (mostExpensive.effective_price ?? 0) - (cheapest.effective_price ?? 0);

  return (
    <div className="rounded-3xl border border-white/10 bg-obsidian-900/90 p-5 shadow-2xl backdrop-blur-xl space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-neon-purple shadow-[0_0_8px_#c084fc]" />
            <h3 className="text-sm font-black tracking-tight text-white uppercase">
              Cross-Platform Arbitrage Spread Matrix
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time spread across {offers.length} certified retailers with landed coupon & delivery cost analysis
          </p>
        </div>

        {maxSavings > 0 && (
          <div className="rounded-full bg-neon-purple/20 border border-neon-purple/40 px-3 py-1 text-xs font-black text-neon-purple font-mono">
            Max Spread Gap: Save {inr(maxSavings)}
          </div>
        )}
      </div>

      {/* Retailer Spread Bars */}
      <div className="space-y-3">
        {sorted.map((offer, idx) => {
          const meta = getRetailerMeta(offer.retailer_name);
          const price = offer.effective_price ?? offer.current_price;
          const diffVsCheapest = price - (cheapest.effective_price ?? price);
          const barWidthPct = Math.max(15, Math.min(100, Math.round((price / maxPrice) * 100)));
          const isBest = idx === 0;

          return (
            <div
              key={offer.listing_id || offer.retailer_name}
              className={`rounded-2xl border p-3.5 transition duration-300 ${
                isBest
                  ? "border-neon-lime/40 bg-obsidian-850 shadow-[0_0_20px_-5px_rgba(212,255,0,0.15)]"
                  : "border-white/5 bg-obsidian-950/60 hover:border-white/15"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                {/* Store Info */}
                <div className="flex items-center gap-3">
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-xl font-black text-xs ${meta.badgeColor}`}
                  >
                    {meta.logoShort}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">{meta.displayName}</span>
                      {isBest && (
                        <span className="rounded-full bg-neon-lime/20 border border-neon-lime/40 px-2 py-0.2 text-[9px] font-black uppercase tracking-wider text-neon-lime">
                          Lowest Landed Price
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {meta.badge} • {meta.deliveryEstimate}
                    </div>
                  </div>
                </div>

                {/* Price & Difference */}
                <div className="text-right flex sm:flex-col items-center sm:items-end justify-between sm:justify-center">
                  <div className="text-sm font-black text-white font-mono">{inr(price)}</div>
                  {diffVsCheapest > 0 ? (
                    <span className="text-[10px] font-mono text-neon-amber font-bold">
                      +{inr(diffVsCheapest)} higher
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono text-neon-lime font-bold">
                      Optimal Target ✓
                    </span>
                  )}
                </div>
              </div>

              {/* Relative Spread Progress Bar */}
              <div className="mt-2.5 flex items-center gap-2">
                <div className="h-1.5 flex-1 rounded-full bg-obsidian-950 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      isBest
                        ? "bg-gradient-to-r from-neon-lime to-emerald-400"
                        : "bg-slate-700"
                    }`}
                    style={{ width: `${barWidthPct}%` }}
                  />
                </div>
                <span className="text-[10px] font-mono text-slate-500 w-12 text-right">
                  {barWidthPct}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
