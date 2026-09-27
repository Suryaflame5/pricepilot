"use client";

import { inr } from "@/lib/formatting";

interface Band {
  label: string;
  lo: number | null | undefined;
  hi: number | null | undefined;
}

interface Props {
  bands: Band[];
  median: number | null | undefined;
  current?: number | null | undefined;
}

/** FORECAST surface: horizon bands. Uncertainty is the product, not a footnote. */
export default function ForecastBand({ bands, median, current }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Projected Price Range</h3>
        <span className="text-xs text-slate-400">calibrated confidence intervals</span>
      </div>
      {current != null && (
        <div className="mt-3 flex items-baseline justify-between border-b border-slate-100 pb-2">
          <span className="text-sm text-slate-500">today</span>
          <span className="text-lg font-bold tabular-nums text-slate-900">{inr(current)}</span>
        </div>
      )}
      <div className="mt-2 space-y-1.5">
        {bands.map((b) => (
          <div key={b.label} className="flex items-baseline justify-between">
            <span className="text-sm text-slate-500">{b.label}</span>
            <span className="font-mono text-sm tabular-nums text-slate-800">
              {b.lo == null || b.hi == null ? (
                <span className="text-slate-300">n/a</span>
              ) : (
                <>
                  {inr(b.lo)} – {inr(b.hi)}
                </>
              )}
            </span>
          </div>
        ))}
      </div>
      {median != null && (
        <div className="mt-3 flex items-baseline justify-between rounded-lg bg-slate-50 px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">30-day median</span>
          <span className="text-lg font-bold tabular-nums text-brand-600">{inr(median)}</span>
        </div>
      )}
    </div>
  );
}