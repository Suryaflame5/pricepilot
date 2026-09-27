"use client";

import { pct } from "@/lib/formatting";

interface Props {
  forecast: number | null | undefined;
  data: number | null | undefined;
  model?: number | null | undefined;
  reasons?: string[];
}

/** RELIABILITY surface: how much should you trust this prediction? */
export default function ReliabilityBadge({ forecast, data, model, reasons }: Props) {
  const rows: { label: string; value: number | null | undefined }[] = [
    { label: "Forecast reliability", value: forecast },
    { label: "Data reliability", value: data },
  ];
  if (model != null) rows.push({ label: "Model reliability", value: model });
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-sm font-semibold text-slate-700">Reliability</div>
      <div className="mt-2 space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-baseline justify-between">
            <span className="text-xs text-slate-500">{r.label}</span>
            <span className="font-mono text-sm font-semibold tabular-nums text-slate-800">
              {r.value == null ? <span className="text-slate-300">n/a</span> : pct(r.value, 0)}
            </span>
          </div>
        ))}
      </div>
      {reasons && reasons.length > 0 && (
        <details className="mt-3 border-t border-slate-100 pt-2">
          <summary className="cursor-pointer text-xs font-medium text-brand-600 hover:underline">
            Why?
          </summary>
          <ul className="mt-2 space-y-1">
            {reasons.map((r, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-slate-600">
                <span className="text-emerald-500">✓</span>
                {r}
              </li>
            ))}
          </ul>
          <div className="mt-2 text-[11px] text-slate-400">
            <button type="button" className="hover:underline">
              How is this calculated?
            </button>
          </div>
        </details>
      )}
    </div>
  );
}