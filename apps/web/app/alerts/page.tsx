"use client";

import { useEffect, useRef, useState } from "react";
import { del, get, post } from "@/lib/api";
import { useRealtimeSubscription } from "@/lib/useRealtime";
import type { Alert, VariantWithProduct } from "@/lib/types";
import RealtimeStatus from "@/components/RealtimeStatus";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [variantId, setVariantId] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [productNames, setProductNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const reloadTimer = useRef<number | null>(null);

  async function load() {
    try {
      const list = await get<Alert[]>("/alerts");
      setAlerts(list);
      const names: Record<string, string> = {};
      for (const a of list) {
        if (!names[a.product_variant_id]) {
          try {
            const v = await get<VariantWithProduct>(`/products/variant/${a.product_variant_id}`);
            names[a.product_variant_id] = v.product?.canonical_name ?? a.product_variant_id;
          } catch {
            names[a.product_variant_id] = a.product_variant_id;
          }
        }
      }
      setProductNames(names);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }

  useEffect(() => {
    load();
  }, []);

  // live alert triggers refresh the list instantly
  useRealtimeSubscription(["alert.triggered"], [], (_type, env) => {
    const payload = env.payload as { alert?: { product_variant_id?: string } };
    setFlash(payload.alert?.product_variant_id ?? "alert");
    if (reloadTimer.current != null) window.clearTimeout(reloadTimer.current);
    reloadTimer.current = window.setTimeout(load, 300);
  });

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!variantId || !targetPrice) return;
    setBusy(true);
    setError(null);
    try {
      await post("/alerts", {
        product_variant_id: variantId,
        target_price: Number(targetPrice),
        direction: "below",
      });
      setTargetPrice("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "create failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await del(`/alerts/${id}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "remove failed");
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Price alerts</h1>
        <div className="flex items-center gap-3">
          {flash && (
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              ● Triggered
            </span>
          )}
          <RealtimeStatus />
        </div>
      </div>
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <form onSubmit={create} className="mb-6 flex flex-wrap gap-2">
        <input
          value={variantId}
          onChange={(e) => setVariantId(e.target.value)}
          placeholder="product variant id (UUID)"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:border-brand-500 focus:outline-none"
        />
        <input
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
          placeholder="target price (₹)"
          type="number"
          className="w-36 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Create alert
        </button>
      </form>

      <div className="space-y-2">
        {alerts.map((a) => (
          <div
            key={a.id}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
          >
            <div>
              <div className="font-medium">{productNames[a.product_variant_id] ?? a.product_variant_id}</div>
              <div className="text-xs text-slate-500">
                alert when price {a.direction} ₹{a.target_price.toLocaleString("en-IN")}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {a.triggered_at ? (
                <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                  triggered
                </span>
              ) : (
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">active</span>
              )}
              <button onClick={() => remove(a.id)} className="text-sm text-red-500 hover:underline">
                remove
              </button>
            </div>
          </div>
        ))}
        {alerts.length === 0 && <p className="text-sm text-slate-500">No alerts yet.</p>}
      </div>
    </div>
  );
}
