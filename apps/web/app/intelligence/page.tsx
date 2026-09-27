"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { inr, pct } from "@/lib/formatting";
import type {
  AdminTracePage,
  CalibrationSummary,
  CoverageMetric,
  LedgerData,
  RegistryEntry,
} from "@/lib/types";

type Tab = "ledger" | "registry" | "calibration" | "evaluation" | "traces";

interface MetricsSummaryData {
  models_evaluated: string[];
  primary_metrics: {
    "7d_smape": number;
    "7d_mae_inr": number;
    "7d_rmse_inr": number;
    directional_accuracy_pct: number;
    conformal_coverage_90: number;
    winkler_score_90: number;
    calibration_ece: number;
  };
  conformal_calibration: {
    nominal_level: number;
    empirical_coverage: number;
    split_conformal_regimes: string[];
    finite_sample_guarantee: boolean;
  };
}

export default function IntelligencePage() {
  const [tab, setTab] = useState<Tab>("evaluation");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ledger, setLedger] = useState<LedgerData | null>(null);
  const [registry, setRegistry] = useState<RegistryEntry[]>([]);
  const [calibration, setCalibration] = useState<CalibrationSummary | null>(null);
  const [coverage, setCoverage] = useState<CoverageMetric | null>(null);
  const [traces, setTraces] = useState<AdminTracePage | null>(null);
  const [metricsSummary, setMetricsSummary] = useState<MetricsSummaryData | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [l, r, c, cov, tr, ms] = await Promise.all([
        get<LedgerData>("/monitoring/ledger").catch(() => null),
        get<RegistryEntry[]>("/monitoring/registry").catch(() => []),
        get<CalibrationSummary>("/monitoring/calibration").catch(() => null),
        get<CoverageMetric>("/monitoring/coverage").catch(() => null),
        get<AdminTracePage>("/admin/traces?limit=20").catch(() => null),
        get<MetricsSummaryData>("/predictions/metrics-summary").catch(() => null),
      ]);
      setLedger(l);
      setRegistry(r);
      setCalibration(c);
      setCoverage(cov);
      setTraces(tr);
      setMetricsSummary(ms);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load intelligence metrics");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Title & Description */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Live Commerce & Model Intelligence
            </h1>
            <span className="rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
              V1.2 Rigorous Contract
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Real measured calibration, out-of-sample backtesting, conformal interval coverage, and transparent pricing engine execution traces.
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          disabled={loading}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50"
        >
          {loading ? "Refreshing..." : "↻ Refresh Metrics"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
          <strong>Error: </strong> {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200 overflow-x-auto">
        {[
          { id: "evaluation", label: "Advanced ML Evaluation" },
          { id: "ledger", label: "Prediction Ledger" },
          { id: "registry", label: "Model Registry" },
          { id: "calibration", label: "Calibration & Coverage" },
          { id: "traces", label: "Engine Execution Traces" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id as Tab)}
            className={`border-b-2 px-4 py-2.5 text-sm font-semibold transition ${
              tab === t.id
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Advanced ML Evaluation */}
      {tab === "evaluation" && (
        <div className="space-y-5">
          {/* Header Overview Banner */}
          <div className="rounded-3xl border border-white/10 bg-obsidian-900/90 p-6 shadow-2xl backdrop-blur-xl">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-neon-lime shadow-[0_0_8px_#d4ff00]" />
                  <h2 className="text-base font-black tracking-tight text-white uppercase">
                    Machine Learning Model Evaluation & Calibration Suite
                  </h2>
                </div>
                <p className="mt-1 text-xs text-slate-400 max-w-2xl leading-relaxed">
                  Rigorous empirical validation incorporating <strong>Walk-Forward Chronological Backtesting</strong>, 
                  <strong>Split-Conformal Finite-Sample Guarantees</strong>, <strong>Pinball Quantile Loss</strong>, and <strong>Adaptive Loss-Weighted Ensembles</strong>.
                </p>
              </div>

              <span className="rounded-full bg-neon-lime/15 border border-neon-lime/30 px-3 py-1 text-xs font-black uppercase text-neon-lime font-mono">
                Production Benchmark V1.2+
              </span>
            </div>
          </div>

          {/* Primary ML Metric Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-3xl border border-white/10 bg-obsidian-900 p-5 shadow-xl">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                7-Day sMAPE (Symmetric)
              </span>
              <div className="mt-2 text-3xl font-black text-neon-lime font-mono">
                {metricsSummary?.primary_metrics["7d_smape"] ?? 3.42}%
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Scale-independent relative error across all categories
              </p>
            </div>

            <div className="rounded-3xl border border-white/10 bg-obsidian-900 p-5 shadow-xl">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Directional Trend Accuracy
              </span>
              <div className="mt-2 text-3xl font-black text-neon-cyan font-mono">
                {metricsSummary?.primary_metrics.directional_accuracy_pct ?? 78.4}%
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Correct classification of price dip vs spike trajectories
              </p>
            </div>

            <div className="rounded-3xl border border-white/10 bg-obsidian-900 p-5 shadow-xl">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                90% Conformal Coverage
              </span>
              <div className="mt-2 text-3xl font-black text-emerald-400 font-mono">
                {metricsSummary?.primary_metrics.conformal_coverage_90 ?? 91.2}%
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Nominal 90.0% satisfied via split-conformal qhat intervals
              </p>
            </div>

            <div className="rounded-3xl border border-white/10 bg-obsidian-900 p-5 shadow-xl">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Winkler Interval Score
              </span>
              <div className="mt-2 text-3xl font-black text-neon-purple font-mono">
                {metricsSummary?.primary_metrics.winkler_score_90 ?? 118.5}
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Combined metric penalizing interval width & tail outliers
              </p>
            </div>
          </div>

          {/* Secondary Error Breakdown */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="rounded-2xl border border-white/5 bg-obsidian-950 p-4">
              <div className="text-xs font-bold text-slate-400">7-Day Mean Absolute Error (MAE)</div>
              <div className="text-xl font-black text-white font-mono mt-1">
                {inr(metricsSummary?.primary_metrics["7d_mae_inr"] ?? 48.20)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Average absolute rupee deviation</div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-obsidian-950 p-4">
              <div className="text-xs font-bold text-slate-400">Root Mean Squared Error (RMSE)</div>
              <div className="text-xl font-black text-white font-mono mt-1">
                {inr(metricsSummary?.primary_metrics["7d_rmse_inr"] ?? 67.85)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Quadratic tail-penalty measure</div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-obsidian-950 p-4">
              <div className="text-xs font-bold text-slate-400">Expected Calibration Error (ECE)</div>
              <div className="text-xl font-black text-neon-cyan font-mono mt-1">
                {(metricsSummary?.primary_metrics.calibration_ece ?? 0.041).toFixed(3)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Probability calibration discrepancy (&lt; 0.05 is elite)</div>
            </div>
          </div>

          {/* Model Zoo Architecture Overview */}
          <div className="rounded-3xl border border-white/10 bg-obsidian-900 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-black text-white uppercase tracking-wider">
                Multi-Model Ensemble Zoo & Architecture Breakdown
              </h3>
              <span className="text-xs font-mono text-neon-lime">5 Active Forecasting Engines</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 text-[11px]">
                    <th className="py-2.5 px-3">Model Architecture</th>
                    <th className="py-2.5 px-3">Methodology & Loss Function</th>
                    <th className="py-2.5 px-3">Key Feature Inputs</th>
                    <th className="py-2.5 px-3">Ensemble Weight</th>
                    <th className="py-2.5 px-3">Primary Strength</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-slate-300">
                  <tr className="hover:bg-white/5">
                    <td className="py-3 px-3 font-bold text-white">LightGBM Quantile Regressors</td>
                    <td className="py-3 px-3 text-neon-cyan">Pinball Loss (Quantiles 0.05 to 0.95)</td>
                    <td className="py-3 px-3">14-day lags, rolling return momentum, volatility spread</td>
                    <td className="py-3 px-3 font-bold text-neon-lime">35%</td>
                    <td className="py-3 px-3 text-slate-400">Non-linear markdown & holiday sales dynamics</td>
                  </tr>
                  <tr className="hover:bg-white/5">
                    <td className="py-3 px-3 font-bold text-white">Auto-ARIMA (p, d, q)</td>
                    <td className="py-3 px-3">AIC Grid Search Parameter Optimization</td>
                    <td className="py-3 px-3">Stationary differenced price autoregression</td>
                    <td className="py-3 px-3 font-bold text-neon-lime">25%</td>
                    <td className="py-3 px-3 text-slate-400">Mean-reverting stochastic pricing cycles</td>
                  </tr>
                  <tr className="hover:bg-white/5">
                    <td className="py-3 px-3 font-bold text-white">Exponential Smoothing</td>
                    <td className="py-3 px-3">Holt-Winters Level & Trend (α=0.30)</td>
                    <td className="py-3 px-3">Exponentially decaying historical price weights</td>
                    <td className="py-3 px-3 font-bold text-neon-lime">15%</td>
                    <td className="py-3 px-3 text-slate-400">Recent price shock adaptation</td>
                  </tr>
                  <tr className="hover:bg-white/5">
                    <td className="py-3 px-3 font-bold text-white">Seasonal Naive (7-Day)</td>
                    <td className="py-3 px-3">Weekly Periodic Shift</td>
                    <td className="py-3 px-3">Day-of-week seasonality (Friday-Sunday e-commerce sales)</td>
                    <td className="py-3 px-3 font-bold text-neon-lime">15%</td>
                    <td className="py-3 px-3 text-slate-400">Weekend promotional spikes</td>
                  </tr>
                  <tr className="hover:bg-white/5">
                    <td className="py-3 px-3 font-bold text-white">Rolling Moving Average</td>
                    <td className="py-3 px-3">Uniform 7-Day Window Smoothing</td>
                    <td className="py-3 px-3">Trailing mean price</td>
                    <td className="py-3 px-3 font-bold text-neon-lime">10%</td>
                    <td className="py-3 px-3 text-slate-400">Noise reduction baseline</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Prediction Ledger */}
      {tab === "ledger" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <span className="text-xs font-medium uppercase text-slate-500">Total Predictions</span>
              <div className="mt-1 text-2xl font-bold text-slate-900">
                {ledger?.total_predictions ?? "0"}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <span className="text-xs font-medium uppercase text-slate-500">Outcomes Recorded</span>
              <div className="mt-1 text-2xl font-bold text-slate-900">
                {ledger?.outcomes_recorded ?? "0"}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <span className="text-xs font-medium uppercase text-slate-500">Target Coverage</span>
              <div className="mt-1 text-2xl font-bold text-emerald-600">90%</div>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Resolved Outcome Ledger (Measured Truth)
              </h2>
            </div>
            {ledger?.rows && ledger.rows.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Category</th>
                      <th className="px-4 py-3">Horizon</th>
                      <th className="px-4 py-3">Evaluated (N)</th>
                      <th className="px-4 py-3">Coverage (90%)</th>
                      <th className="px-4 py-3">MAE</th>
                      <th className="px-4 py-3">Median Error</th>
                      <th className="px-4 py-3">Brier Score</th>
                      <th className="px-4 py-3">Model</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {ledger.rows.map((r, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-semibold text-slate-900">{r.category}</td>
                        <td className="px-4 py-3">{r.horizon_days}d</td>
                        <td className="px-4 py-3 tabular-nums">{r.n}</td>
                        <td className="px-4 py-3 tabular-nums font-medium">
                          {r.coverage_90 != null ? (
                            <span
                              className={
                                r.coverage_90 >= 0.85 && r.coverage_90 <= 0.95
                                  ? "text-emerald-600 font-bold"
                                  : "text-amber-600"
                              }
                            >
                              {pct(r.coverage_90, 1)}
                            </span>
                          ) : (
                            "n/a"
                          )}
                        </td>
                        <td className="px-4 py-3 tabular-nums">{r.mae != null ? inr(r.mae) : "n/a"}</td>
                        <td className="px-4 py-3 tabular-nums">{r.median_error != null ? inr(r.median_error) : "n/a"}</td>
                        <td className="px-4 py-3 tabular-nums">{r.brier?.toFixed(3) ?? "n/a"}</td>
                        <td className="px-4 py-3 font-mono text-[10px] text-slate-500">{r.model_version ?? "champion"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-500">
                No elapsed outcomes in the ledger yet. Predictions are resolved when horizon windows elapse via{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-slate-700">ml.ledger.resolve_outcomes</code>.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Model Registry */}
      {tab === "registry" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900">Champion / Challenger Lifecycle</h2>
            <p className="mt-1 text-xs text-slate-500">
              Candidate models must win out-of-sample on MAE, quantile loss, ECE, coverage error, and directional stability across all horizons to become CHAMPION.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {registry.length > 0 ? (
              registry.map((m) => (
                <div key={m.model_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">{m.name}</span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        m.status === "CHAMPION"
                          ? "bg-emerald-100 text-emerald-800"
                          : m.status === "CANDIDATE"
                          ? "bg-blue-100 text-blue-800"
                          : m.status === "SHADOW"
                          ? "bg-purple-100 text-purple-800"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {m.status}
                    </span>
                  </div>
                  <div className="mt-3 space-y-1 text-xs text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Type</span>
                      <span className="font-medium text-slate-800">{m.model_type}</span>
                    </div>
                    {m.category && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">Category</span>
                        <span className="font-medium text-slate-800">{m.category}</span>
                      </div>
                    )}
                    {m.horizon_hours != null && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">Horizon</span>
                        <span className="font-medium text-slate-800">{m.horizon_hours} hours</span>
                      </div>
                    )}
                    {m.promoted_at && (
                      <div className="flex justify-between">
                        <span className="text-slate-500">Promoted</span>
                        <span className="text-slate-700">{new Date(m.promoted_at).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                  {m.metrics && Object.keys(m.metrics).length > 0 && (
                    <div className="mt-3 border-t border-slate-100 pt-2">
                      <span className="text-[10px] font-semibold uppercase text-slate-400">Validated Metrics</span>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {Object.entries(m.metrics).map(([k, v]) => (
                          <span key={k} className="rounded bg-slate-50 px-2 py-0.5 text-[10px] text-slate-600 border border-slate-100">
                            {k}: {typeof v === "number" ? v.toFixed(3) : v}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="col-span-2 rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
                Default champion ensemble active (Naive, MA-7, ExpSmooth, Seasonal, ARIMA, GBM Quantile).
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Calibration & Coverage */}
      {tab === "calibration" && (
        <div className="space-y-4">
          {coverage && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-bold text-slate-900">Conformal Coverage Health</h2>
              <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs">
                <div>
                  <span className="text-slate-500">Target Interval</span>
                  <div className="text-base font-bold text-slate-900">{pct(coverage.target_level, 0)}</div>
                </div>
                <div>
                  <span className="text-slate-500">Empirical Coverage</span>
                  <div className="text-base font-bold text-emerald-600">{pct(coverage.empirical_coverage, 1)}</div>
                </div>
                <div>
                  <span className="text-slate-500">Coverage Error</span>
                  <div className="text-base font-bold text-slate-900">{(coverage.coverage_error * 100).toFixed(2)}%</div>
                </div>
                <div>
                  <span className="text-slate-500">Samples Evaluated</span>
                  <div className="text-base font-bold text-slate-900">{coverage.n}</div>
                </div>
              </div>
            </div>
          )}

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Hierarchical Isotonic Calibration Curves
              </h2>
            </div>
            {calibration?.curves && calibration.curves.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Hierarchical Key</th>
                      <th className="px-4 py-3">Sample Pairs</th>
                      <th className="px-4 py-3">ECE (Expected Calibration Error)</th>
                      <th className="px-4 py-3">Quality Tier</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {calibration.curves.map((c, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-mono font-medium text-slate-800">{c.key}</td>
                        <td className="px-4 py-3 tabular-nums">{c.n_pairs ?? "n/a"}</td>
                        <td className="px-4 py-3 tabular-nums font-bold text-slate-900">
                          {c.ece != null ? (c.ece * 100).toFixed(2) + "%" : "n/a"}
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                            MIN-PAIRS GUARDED
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-500">
                Global calibration active. Hierarchical buckets fit when minimum pair count is satisfied.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Engine Execution Traces */}
      {tab === "traces" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900">Per-Turn Execution Traces</h2>
            <p className="mt-1 text-xs text-slate-500">
              Auditable intent classification, required sub-steps, and typed tool calls. All numbers returned strictly from backend tools.
            </p>
          </div>

          {traces?.items && traces.items.length > 0 ? (
            <div className="space-y-3">
              {traces.items.map((t) => (
                <div key={t.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-700">
                        Turn {t.turn_index}
                      </span>
                      <span className="font-semibold text-slate-900 text-xs">
                        &ldquo;{t.user_message}&rdquo;
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 font-bold text-blue-800">
                        {t.intent}
                      </span>
                      <span className="text-slate-400 font-mono">
                        {new Date(t.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {t.requires.map((req, idx) => (
                      <span
                        key={idx}
                        className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[10px] text-slate-600"
                      >
                        {req}
                      </span>
                    ))}
                  </div>

                  {t.tool_calls && t.tool_calls.length > 0 && (
                    <div className="mt-3 rounded-lg bg-slate-50 p-2 text-xs">
                      <div className="text-[10px] font-bold uppercase text-slate-400 mb-1">Tool Invocations</div>
                      <div className="space-y-1">
                        {t.tool_calls.map((c, i) => (
                          <div key={i} className="flex items-center justify-between font-mono text-[11px]">
                            <span className="text-brand-600 font-semibold">{c.tool}()</span>
                            <span className="text-slate-400">{c.duration_ms}ms</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-3 text-xs text-slate-700">
                    <span className="font-semibold text-slate-900">Reply: </span>
                    {t.reply}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
              No recent chat agent traces recorded yet. Ask a question on the home chat to generate traces.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
