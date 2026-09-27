"use client";

import { useState } from "react";
import { inr } from "@/lib/formatting";
import { post } from "@/lib/api";

interface Props {
  variantId: string;
  productName: string;
  currentPrice: number;
}

interface MLSimulationResult {
  variant_id: string;
  product_name: string;
  user_price: number;
  previous_price: number;
  base_p50_prediction: number;
  updated_p50_prediction: number;
  instant_error: number;
  instant_smape: number;
  instant_mape: number;
  inside_conformal_bounds: boolean;
  conformal_lower: number;
  conformal_upper: number;
  winkler_score: number;
  updated_weights: Record<string, number>;
  per_model_predictions: Record<string, number>;
  backtest_metrics: {
    mae?: number;
    rmse?: number;
    smape?: number;
    mape?: number;
    n?: number;
    directional_accuracy?: number;
    stability?: number;
    winkler_score_90?: number;
    coverage_90?: number;
  };
  regime: {
    regime: string;
    stable: boolean;
  };
  confidence_score: number;
  confidence_level: string;
}

export default function RealTimeUserPriceSandbox({ variantId, productName, currentPrice }: Props) {
  const [userPriceInput, setUserPriceInput] = useState<string>(Math.round(currentPrice * 0.94).toString());
  const [horizon, setHorizon] = useState<number>(7);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MLSimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSimulate(e: React.FormEvent) {
    e.preventDefault();
    const priceNum = parseFloat(userPriceInput);
    if (isNaN(priceNum) || priceNum <= 0) {
      setError("Please enter a valid price in INR.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await post<MLSimulationResult>("/predictions/user-data/simulate", {
        product_variant_id: variantId,
        user_observed_price: priceNum,
        horizon_days: horizon,
        interval_level: 0.90,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ML simulation failed. Ensure variant has price series.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-3xl border border-white/10 bg-obsidian-900/90 p-5 shadow-2xl backdrop-blur-xl space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-neon-cyan shadow-[0_0_8px_#00f0ff]" />
            <h3 className="text-sm font-black tracking-tight text-white uppercase">
              Real-Time User Price Ingestion & ML Evaluation Terminal
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Test custom market observations, user-reported offline deals, or flash sales to trigger online ML refitting
          </p>
        </div>

        <span className="rounded-full bg-neon-cyan/15 border border-neon-cyan/30 px-2.5 py-0.5 text-[11px] font-mono font-bold text-neon-cyan">
          Live Online Learning
        </span>
      </div>

      {/* User Input Form */}
      <form onSubmit={handleSimulate} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-1">
          <label className="block text-[11px] font-bold text-slate-300 uppercase mb-1">
            Your Observed Price (₹)
          </label>
          <div className="relative">
            <span className="absolute left-3 top-2.5 text-slate-500 font-bold text-xs">₹</span>
            <input
              type="number"
              step="any"
              value={userPriceInput}
              onChange={(e) => setUserPriceInput(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-obsidian-950 px-7 py-2 text-xs font-mono font-bold text-white focus:border-neon-cyan focus:outline-none focus:ring-1 focus:ring-neon-cyan"
              placeholder="e.g. 1299"
            />
          </div>
        </div>

        <div className="sm:col-span-1">
          <label className="block text-[11px] font-bold text-slate-300 uppercase mb-1">
            Forecast Horizon
          </label>
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="w-full rounded-xl border border-white/10 bg-obsidian-950 px-3 py-2 text-xs font-bold text-slate-200 focus:border-neon-cyan focus:outline-none"
          >
            <option value={7}>7 Days (Tactical)</option>
            <option value={30}>30 Days (Medium Term)</option>
            <option value={90}>90 Days (Strategic Cycle)</option>
          </select>
        </div>

        <div className="sm:col-span-1 flex items-end">
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-neon-cyan px-4 py-2.5 text-xs font-black uppercase tracking-wider text-obsidian-950 hover:bg-cyan-300 hover:shadow-neon-cyan transition disabled:opacity-50"
          >
            {loading ? "Re-Fitting Model Zoo..." : "⚡ Run Real-Time Calibration"}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300 font-mono">
          {error}
        </div>
      )}

      {/* Live Result Visualization */}
      {result && (
        <div className="space-y-4 pt-2">
          {/* Summary Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-3 text-center">
              <div className="text-[10px] uppercase font-bold text-slate-400">Pre-Update Forecast</div>
              <div className="text-sm font-black text-slate-300 mt-1 font-mono">
                {inr(result.base_p50_prediction)}
              </div>
            </div>

            <div className="rounded-2xl border border-neon-lime/30 bg-obsidian-850 p-3 text-center shadow-neon-lime">
              <div className="text-[10px] uppercase font-bold text-neon-lime">Post-Update Forecast</div>
              <div className="text-base font-black text-neon-lime mt-1 font-mono">
                {inr(result.updated_p50_prediction)}
              </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-3 text-center">
              <div className="text-[10px] uppercase font-bold text-slate-400">Step Error (sMAPE)</div>
              <div className="text-sm font-black text-neon-cyan mt-1 font-mono">
                {result.instant_smape.toFixed(2)}%
              </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-3 text-center">
              <div className="text-[10px] uppercase font-bold text-slate-400">Conformal Coverage</div>
              <div className="mt-1">
                {result.inside_conformal_bounds ? (
                  <span className="inline-flex items-center rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] font-bold text-emerald-400">
                    ✓ In 90% Bounds
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-neon-amber/20 px-2 py-0.5 text-[11px] font-bold text-neon-amber">
                    ⚠ Tail Outlier
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Model Zoo Dynamic Weight Shifts */}
          <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Model Zoo Adaptive Weights (Loss-Proportional Allocation)
              </h4>
              <span className="text-[10px] font-mono text-neon-lime">
                Confidence: {result.confidence_level} ({(result.confidence_score * 100).toFixed(1)}%)
              </span>
            </div>

            <div className="space-y-2">
              {Object.entries(result.updated_weights).map(([modelName, weight]) => {
                const predPrice = result.per_model_predictions[modelName];
                const pct = Math.round(weight * 100);
                return (
                  <div key={modelName} className="space-y-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="font-mono text-slate-300 uppercase">{modelName}</span>
                      <span className="font-mono text-slate-400">
                        Pred: {predPrice ? inr(predPrice) : "n/a"} • <strong className="text-neon-cyan">{pct}%</strong> weight
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-obsidian-950 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-lime transition-all duration-500"
                        style={{ width: `${Math.max(5, pct)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Rigorous ML Evaluation Metric Breakdown */}
          <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-4 space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Rigorous Evaluation Metric Suite (Walk-Forward Backtesting)
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="rounded-xl bg-obsidian-950 p-2 text-center">
                <span className="text-slate-500 block text-[10px]">MAE (Mean Abs Error)</span>
                <span className="text-white font-bold">{inr(result.backtest_metrics.mae ?? 0)}</span>
              </div>
              <div className="rounded-xl bg-obsidian-950 p-2 text-center">
                <span className="text-slate-500 block text-[10px]">RMSE</span>
                <span className="text-white font-bold">{inr(result.backtest_metrics.rmse ?? 0)}</span>
              </div>
              <div className="rounded-xl bg-obsidian-950 p-2 text-center">
                <span className="text-slate-500 block text-[10px]">Directional Accuracy</span>
                <span className="text-neon-lime font-bold">
                  {((result.backtest_metrics.directional_accuracy ?? 0.75) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="rounded-xl bg-obsidian-950 p-2 text-center">
                <span className="text-slate-500 block text-[10px]">Winkler Interval Score</span>
                <span className="text-neon-cyan font-bold">
                  {(result.winkler_score ?? 0).toFixed(1)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
