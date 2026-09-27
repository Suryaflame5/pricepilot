"use client";

import { useEffect, useState } from "react";
import { get, inr } from "@/lib/api";
import type { Compare, PriceHistory } from "@/lib/types";
import PriceChart from "@/components/PriceChart";

export default function HistoryPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { listing?: string };
}) {
  const [history, setHistory] = useState<PriceHistory | null>(null);
  const [productName, setProductName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const p = await get<{ canonical_name: string }>(`/products/${params.id}`);
        setProductName(p.canonical_name);
        let listingId = searchParams.listing;
        if (!listingId) {
          const detail = await get<{ variants: { id: string }[] }>(`/products/${params.id}`);
          const variant = detail.variants[0];
          if (!variant) return;
          const c = await get<Compare>(`/products/variant/${variant.id}/compare`);
          listingId = c.cheapest?.listing_id;
        }
        if (!listingId) return;
        const h = await get<PriceHistory>(`/prices/history?listing_id=${listingId}&resample=1d&since_days=365`);
        setHistory(h);
      } catch (err) {
        setError(err instanceof Error ? err.message : "load failed");
      }
    })();
  }, [params.id, searchParams.listing]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!history) return <p className="text-slate-400">Loading…</p>;

  const points = history.points.map((p) => ({ t: p.t, price: p.price }));

  return (
    <div>
      <a href={`/product/${params.id}`} className="text-sm text-brand-600 hover:underline">
        ← {productName || "back"}
      </a>
      <h1 className="mb-4 mt-2 text-xl font-bold">Price history (365 days)</h1>
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <PriceChart points={points} />
        <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Latest</div>
            <div className="font-semibold">{inr(points[points.length - 1].price)}</div>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs text-slate-500">90d min</div>
            <div className="font-semibold">{inr(Math.min(...points.slice(-90).map((p) => p.price)))}</div>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-xs text-slate-500">90d max</div>
            <div className="font-semibold">{inr(Math.max(...points.slice(-90).map((p) => p.price)))}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
