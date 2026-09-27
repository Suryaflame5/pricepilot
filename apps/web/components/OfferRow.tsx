"use client";

import { inr } from "@/lib/formatting";

interface Props {
  retailer: string;
  effectivePrice: number | null | undefined;
  availability?: string | null;
  url?: string | null;
  best?: boolean;
  note?: string | null;
  onBuy?: (() => void) | null;
}

/** One retailer row in a market comparison. */
export default function OfferRow({ retailer, effectivePrice, availability, url, best, note, onBuy }: Props) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-800">{retailer}</span>
        {best && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-800">
            Best
          </span>
        )}
        {note && <span className="text-xs text-slate-400">{note}</span>}
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <div className="text-lg font-bold tabular-nums text-slate-900">
            {effectivePrice == null ? (
              <span className="text-sm font-normal text-slate-400">n/a</span>
            ) : (
              inr(effectivePrice)
            )}
          </div>
          <div className="text-[11px] text-slate-500">
            {url ? (
              <a href={url} target="_blank" rel="noreferrer" className="hover:text-brand-600 hover:underline">
                view listing
              </a>
            ) : (
              (availability ?? "")
            )}
          </div>
        </div>
        {onBuy && (
          <button
            type="button"
            onClick={onBuy}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-brand-700"
          >
            Buy
          </button>
        )}
      </div>
    </div>
  );
}