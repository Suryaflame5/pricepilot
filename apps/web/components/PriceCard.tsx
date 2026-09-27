"use client";

import { inr } from "@/lib/formatting";
import { deltaPct } from "@/lib/formatting";

interface Props {
  price: number | null | undefined;
  label?: string | null;
  sub?: string | null;
  previousPrice?: number | null | undefined;
  best?: boolean;
}

/** PRIMARY surface: the number the user cares about, rendered large. */
export default function PriceCard({ price, label, sub, previousPrice, best }: Props) {
  const delta = deltaPct(previousPrice, price);
  return (
    <div className="flex items-baseline justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label ?? "Current price"}
        </div>
        <div className="mt-1 text-3xl font-bold tabular-nums text-slate-900">
          {inr(price)}
          {best && (
            <span className="ml-2 rounded-full bg-brand-600 px-2 py-0.5 align-middle text-xs font-semibold text-white">
              Best
            </span>
          )}
        </div>
        {sub && <div className="mt-0.5 text-sm text-slate-500">{sub}</div>}
      </div>
      {delta && (
        <div className="rounded-lg bg-amber-50 px-2 py-1 text-sm font-semibold tabular-nums text-amber-700">
          {delta}
        </div>
      )}
    </div>
  );
}