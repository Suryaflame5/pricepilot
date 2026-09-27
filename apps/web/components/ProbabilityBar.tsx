"use client";

import { pct } from "@/lib/formatting";

interface Props {
  label?: string;
  value: number | null | undefined; // 0..1
  targetText?: string | null;
}

/** PROBABILITY surface: how likely is YOUR target? */
export default function ProbabilityBar({ label, value, targetText }: Props) {
  const v = value == null ? 0 : Math.max(0, Math.min(1, value));
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-slate-600">{label ?? "Target probability"}</span>
        <span className="text-sm font-bold tabular-nums text-slate-900">{pct(value, 0)}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-600 transition-all"
          style={{ width: `${v * 100}%` }}
        />
      </div>
      {targetText && <div className="mt-1 text-[11px] text-slate-400">{targetText}</div>}
    </div>
  );
}