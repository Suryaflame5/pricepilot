"use client";

import { useState } from "react";
import { useRealtimeState } from "@/lib/useRealtime";

const META: Record<string, { dot: string; label: string; text: string }> = {
  live: { dot: "bg-emerald-500", label: "Live", text: "Connected" },
  connecting: { dot: "bg-slate-400 animate-pulse", label: "Connecting", text: "Connecting…" },
  reconnecting: { dot: "bg-amber-400 animate-pulse", label: "Reconnecting", text: "Reconnecting…" },
  degraded: { dot: "bg-amber-400", label: "Degraded", text: "Degraded — updates slow" },
  offline: { dot: "bg-slate-300", label: "Offline", text: "Live updates unavailable" },
};

function ago(ts: number | null): string {
  if (ts == null) return "never";
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  return `${Math.round(s / 60)}m ago`;
}

/** Subtle connection pill; click for details. REST is always the fallback. */
export default function RealtimeStatus() {
  const snap = useRealtimeState();
  const [open, setOpen] = useState(false);
  const meta = META[snap.state] ?? META.offline;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:border-brand-500"
        title="Real-time connection status"
      >
        <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
        {meta.label}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-lg">
          <div className="font-semibold text-slate-800">Live connection</div>
          <dl className="mt-2 space-y-1 text-slate-500">
            <div className="flex justify-between">
              <dt>Status</dt>
              <dd className="font-medium text-slate-700">{meta.text}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Last event</dt>
              <dd className="tabular-nums">{ago(snap.lastEventAt)}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Events received</dt>
              <dd className="tabular-nums">{snap.eventsReceived}</dd>
            </div>
          </dl>
          {snap.state === "offline" && (
            <p className="mt-2 border-t border-slate-100 pt-2 text-[11px] text-slate-400">
              Real-time unavailable — pages stay fresh via REST snapshots.
            </p>
          )}
        </div>
      )}
    </div>
  );
}