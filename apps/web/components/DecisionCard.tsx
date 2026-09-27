"use client";

import { inr, pct, RECO_LABEL, type Recommendation } from "@/lib/formatting";

interface Props {
  recommendation: Recommendation | string;
  expectedSaving?: number | null;
  probabilityOfBenefit?: number | null;
  targetProbability?: number | null;
  expectedPrice?: number | null;
  horizonDays?: number | null;
  reasoning?: string[];
  onSetAlert?: (() => void) | null;
  onBuy?: (() => void) | null;
}

export default function DecisionCard({
  recommendation,
  expectedSaving,
  probabilityOfBenefit,
  targetProbability,
  expectedPrice,
  horizonDays,
  reasoning,
  onSetAlert,
  onBuy,
}: Props) {
  const isBuyNow =
    typeof recommendation === "string" &&
    (recommendation.toLowerCase().includes("buy") || recommendation === "BUY_NOW");

  const timingScore = isBuyNow ? 92 : 46;

  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/60 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <div className={`h-2.5 w-2.5 rounded-full ${isBuyNow ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
            Optimal Purchase Window
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-slate-400">Opportunity Score:</span>
          <span
            className={`rounded-full px-3 py-0.5 text-xs font-black shadow-xs ${
              isBuyNow
                ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                : "bg-amber-100 text-amber-900 border border-amber-200"
            }`}
          >
            {timingScore}/100 • {isBuyNow ? "STRONG BUY" : "WAIT FOR DIP"}
          </span>
        </div>
      </div>

      {/* Visual Timing Bar */}
      <div className="px-5 pt-4">
        <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1.5 font-medium">
          <span>Historical Peak</span>
          <span>Fair Market Value</span>
          <span className="text-emerald-700 font-bold">Best Entry Price</span>
        </div>
        <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden flex">
          <div className="h-full bg-rose-300 w-1/4" />
          <div className="h-full bg-amber-300 w-2/4" />
          <div className={`h-full ${isBuyNow ? "bg-emerald-500" : "bg-slate-300"} w-1/4`} />
        </div>
      </div>

      {/* Numerical Evidence Matrix */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 px-5 py-4 text-xs">
        {expectedPrice != null && (
          <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-100">
            <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Projected Price</span>
            <span className="font-black text-sm text-slate-900 tabular-nums">{inr(expectedPrice)}</span>
          </div>
        )}

        {expectedSaving != null && expectedSaving > 0 && (
          <div className="rounded-xl bg-emerald-50/60 p-2.5 border border-emerald-100">
            <span className="text-emerald-600 block text-[10px] uppercase font-bold tracking-wider">Projected Savings</span>
            <span className="font-black text-sm text-emerald-800 tabular-nums">{inr(expectedSaving)}</span>
          </div>
        )}

        {probabilityOfBenefit != null && (
          <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-100">
            <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Dip Probability</span>
            <span className="font-black text-sm text-slate-900 tabular-nums">{pct(probabilityOfBenefit, 0)}</span>
          </div>
        )}

        {horizonDays != null && (
          <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-100">
            <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Analysis Horizon</span>
            <span className="font-black text-sm text-slate-900 tabular-nums">{horizonDays} Days</span>
          </div>
        )}
      </div>

      {/* Reasoning Points */}
      {reasoning && reasoning.length > 0 && (
        <div className="border-t border-slate-100 bg-slate-50/30 px-5 py-3 text-xs text-slate-600">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
            Market Context & Signals
          </div>
          <ul className="space-y-1">
            {reasoning.slice(0, 3).map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-emerald-600 font-bold">›</span>
                <span className="leading-snug">{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Buttons */}
      {(onSetAlert || onBuy) && (
        <div className="flex gap-2.5 border-t border-slate-100 px-5 py-3.5 bg-white">
          {onBuy && (
            <button
              type="button"
              onClick={onBuy}
              className="flex-1 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white hover:bg-brand-600 transition shadow-sm"
            >
              Lock In Price & Buy
            </button>
          )}
          {onSetAlert && (
            <button
              type="button"
              onClick={onSetAlert}
              className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 hover:border-slate-400 hover:bg-slate-50 transition"
            >
              Track Price Drop
            </button>
          )}
        </div>
      )}
    </div>
  );
}