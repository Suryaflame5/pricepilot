"use client";

import type { Variant } from "@/lib/types";

interface Props {
  item: Variant;
}

/** Watchlist strip item on the home screen — AI monitoring center entry point. */
export default function WatchlistCard({ item }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="truncate text-sm font-semibold text-slate-800">
        {item.variant_name ?? "Untitled product"}
      </div>
      <div className="mt-0.5 truncate text-xs text-slate-500">
        {[item.color ?? "", item.storage ?? ""].filter(Boolean).join(" · ") || "—"}
      </div>
      <div className="mt-2 text-[11px] font-medium text-brand-600">
        <a href="/watchlist" className="hover:underline">
          View intelligence →
        </a>
      </div>
    </div>
  );
}