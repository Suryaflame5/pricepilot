"use client";

import { useEffect, useRef, useState } from "react";
import { del, get } from "@/lib/api";
import { useRealtimeSubscription } from "@/lib/useRealtime";
import type { Variant } from "@/lib/types";
import RealtimeStatus from "@/components/RealtimeStatus";

const WATCH_TOPICS = [
  "price.changed",
  "price.dropped",
  "price.spike",
  "promotion.started",
  "promotion.ended",
  "prediction.updated",
  "decision.changed",
  "alert.triggered",
];

export default function WatchlistPage() {
  const [items, setItems] = useState<Variant[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [livePulse, setLivePulse] = useState(false);
  const reloadTimer = useRef<number | null>(null);

  async function load() {
    try {
      const list = await get<Variant[]>("/watchlist");
      setItems(list);
      setLivePulse(true);
      window.setTimeout(() => setLivePulse(false), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }

  useEffect(() => {
    load();
  }, []);

  // live incremental refresh: any event touching a watched variant reloads it
  useRealtimeSubscription(WATCH_TOPICS, items.map((i) => i.id), () => {
    if (reloadTimer.current != null) window.clearTimeout(reloadTimer.current);
    reloadTimer.current = window.setTimeout(load, 400);
  });

  async function remove(id: string) {
    try {
      await del(`/watchlist/${id}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "remove failed");
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Watchlist</h1>
        <div className="flex items-center gap-3">
          {livePulse && (
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              ● Updated
            </span>
          )}
          <RealtimeStatus />
        </div>
      </div>
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {items.length === 0 && (
        <p className="text-sm text-slate-500">
          Nothing tracked yet. Add products from their page with the "+ Watchlist" button.
        </p>
      )}
      <div className="space-y-2">
        {items.map((v) => (
          <div
            key={v.id}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
          >
            <div>
              <div className="font-medium">{v.variant_name ?? v.id}</div>
              <div className="text-xs text-slate-500">{v.color ?? "—"}</div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => remove(v.id)} className="text-sm text-red-500 hover:underline">
                remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}