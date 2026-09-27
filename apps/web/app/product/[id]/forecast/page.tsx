"use client";

import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import type { Compare, Decision, PricePrediction, ProductDetail, TargetProbability } from "@/lib/types";
import ForecastCard from "@/components/ForecastCard";

export default function ForecastPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<{
    product: ProductDetail;
    prediction: PricePrediction;
    target: TargetProbability;
    decision: Decision;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const product = await get<ProductDetail>(`/products/${params.id}`);
        const variant = product.variants[0];
        if (!variant) {
          setError("no variants for this product");
          return;
        }
        const c = await get<Compare>(`/products/variant/${variant.id}/compare`);
        const targetPrice = Math.round((c.cheapest?.effective_price ?? 29990) * 0.9);

        const [prediction, target, decision] = await Promise.all([
          post<PricePrediction>("/predictions/price", {
            product_variant_id: variant.id,
            horizon_hours: 720,
            interval_level: 0.9,
          }),
          post<TargetProbability>("/predictions/target", {
            product_variant_id: variant.id,
            target_price: targetPrice,
            horizons_hours: [168, 720, 2160],
          }),
          post<Decision>("/predictions/decision", {
            product_variant_id: variant.id,
            target_price: targetPrice,
            urgency: "normal",
          }),
        ]);
        setData({ product, prediction, target, decision });
      } catch (err) {
        setError(err instanceof Error ? err.message : "forecast failed");
      }
    })();
  }, [params.id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-slate-400">Computing forecast… this runs the model ensemble and may take ~30s.</p>;

  return (
    <div>
      <a href={`/product/${params.id}`} className="text-sm text-brand-600 hover:underline">
        ← {data.product.canonical_name}
      </a>
      <h1 className="mb-4 mt-2 text-xl font-bold">Prediction dashboard</h1>
      {data.prediction.warnings.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {data.prediction.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <ForecastCard prediction={data.prediction} target={data.target} decision={data.decision} />
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="font-semibold">Reliability (backtest)</h3>
            <dl className="mt-3 space-y-1.5 text-sm">
              <Row k="Historical coverage (90%)" v={data.prediction.reliability.historical_coverage?.toFixed(2)} />
              <Row k="Calibration error (ECE)" v={data.prediction.reliability.calibration_error?.toFixed(3)} />
              <Row k="Backtest MAE (1d)" v={data.prediction.reliability.historical_mae?.toFixed(0)} />
              <Row k="Backtest samples" v={String(data.prediction.reliability.samples)} />
              <Row k="Model version" v={data.prediction.model_version} />
            </dl>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="font-semibold">Why this confidence?</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
              {data.prediction.confidence.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string | null | undefined }) {
  if (v == null) return null;
  return (
    <div className="flex justify-between">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-mono">{v}</dd>
    </div>
  );
}
