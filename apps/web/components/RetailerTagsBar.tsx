"use client";

import { RETAILER_METADATA } from "@/lib/retailers";

interface RetailerTagsBarProps {
  selectedRetailer?: string | null;
  onSelectRetailer?: (retailerId: string | null) => void;
}

export default function RetailerTagsBar({
  selectedRetailer = null,
  onSelectRetailer,
}: RetailerTagsBarProps) {
  const retailers = Object.values(RETAILER_METADATA);

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-2 scrollbar-none">
      <button
        type="button"
        onClick={() => onSelectRetailer && onSelectRetailer(null)}
        className={`flex-shrink-0 rounded-full px-3.5 py-1.5 text-xs font-bold transition shadow-sm ${
          selectedRetailer === null
            ? "bg-slate-900 text-white"
            : "border border-slate-200 bg-white text-slate-700 hover:border-slate-300"
        }`}
      >
        🌐 All Stores
      </button>

      {retailers.map((r) => {
        const isSelected = selectedRetailer === r.id;
        return (
          <button
            key={r.id}
            type="button"
            onClick={() => onSelectRetailer && onSelectRetailer(isSelected ? null : r.id)}
            className={`flex-shrink-0 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold border transition ${
              isSelected
                ? "bg-slate-900 border-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
            }`}
          >
            <span className="font-mono text-[10px] text-slate-500 font-bold">{r.logoShort}</span>
            <span>{r.displayName}</span>
          </button>
        );
      })}
    </div>
  );
}
