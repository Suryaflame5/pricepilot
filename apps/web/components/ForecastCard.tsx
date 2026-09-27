"use client";

import { inr } from "@/lib/api";
import type { Decision, PricePrediction, TargetProbability } from "@/lib/types";
import ConfidenceBadge from "./ConfidenceBadge";

interface Props {
  prediction: PricePrediction;
  target: TargetProbability;
  decision: Decision;
}

export default function ForecastCard({ prediction, target, decision }: Props) {
  const f = prediction.forecast;
  const wait = target.recommended_wait_window;

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-base font-black text-slate-900">Price Trajectory & Forecast</h3>
          <p className="text-xs text-slate-400">Statistical market projections across major sales cycles</p>
        </div>
        <ConfidenceBadge level={prediction.confidence.level} score={prediction.confidence.score} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-2xl bg-slate-50 p-3.5 border border-slate-100">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">30-Day Median Projection</span>
          <span className="text-2xl font-black text-slate-900">{inr(f.p50)}</span>
        </div>

        <div className="rounded-2xl bg-slate-50 p-3.5 border border-slate-100">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
            {(prediction.interval.level * 100).toFixed(0)}% Confidence Interval
          </span>
          <span className="text-base font-bold text-slate-800">
            {inr(prediction.interval.lower)} – {inr(prediction.interval.upper)}
          </span>
        </div>
      </div>

      <div className="space-y-2 border-t border-slate-100 pt-3 text-xs">
        <div className="flex justify-between text-slate-600">
          <span>7-Day to 30-Day Projected Band:</span>
          <span className="font-bold text-slate-900">
            {inr(f.p05)} – {inr(f.p95)}
          </span>
        </div>
        <div className="flex justify-between text-slate-600">
          <span>Desired Target ({inr(target.target_price)}):</span>
          <span className="font-bold text-emerald-700">
            {(target.probabilities["30d"] ?? 0).toFixed(0)}% Probability
          </span>
        </div>
        {wait && (
          <div className="flex justify-between text-slate-600">
            <span>Optimal Expected Wait Window:</span>
            <span className="font-bold text-brand-600">
              Day {wait.start_day} – {wait.end_day}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
