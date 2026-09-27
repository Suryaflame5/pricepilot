"use client";

import type { ChatStep } from "@/lib/types";

interface Props {
  steps: ChatStep[];
  busy?: boolean;
  busyLabel?: string | null;
}

const KIND_LABEL: Record<string, string> = {
  SEARCH: "products searched",
  COMPARE: "offers compared",
  HISTORY: "history analyzed",
  FORECAST: "forecast generated",
  DECIDE: "decision calculated",
  ALERT: "alert registered",
  TARGET: "target checked",
};

/** AI activity, visible but unobtrusive: "checking 7 retailers… ✓ 7 checked". */
export default function ToolActivity({ steps, busy, busyLabel }: Props) {
  const label = KIND_LABEL[steps[steps.length - 1]?.kind] ?? "working…";
  return (
    <div className="space-y-0.5 text-xs text-slate-500">
      {busy && (
        <div className="flex items-center gap-2 text-slate-400">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" />
          PricePilot is {busyLabel ?? label}
          <span className="animate-pulse">…</span>
        </div>
      )}
      {steps.map((s, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <span className="text-emerald-500">✓</span>
          <span>{s.summary}</span>
        </div>
      ))}
    </div>
  );
}