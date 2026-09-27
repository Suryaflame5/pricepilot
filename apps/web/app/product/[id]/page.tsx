"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { get, post } from "@/lib/api";
import { inr, priceDelta } from "@/lib/formatting";
import { useLiveProduct } from "@/lib/useLiveProduct";
import { useRealtimeState } from "@/lib/useRealtime";
import { useCart } from "@/lib/cartContext";
import { getProductImages } from "@/lib/productImages";
import { getRetailerMeta } from "@/lib/retailers";
import type {
  Compare,
  Decision,
  PriceHistory,
  PricePrediction,
  PriceStats,
  ProductDetail,
  TargetProbability,
} from "@/lib/types";
import DecisionCard from "@/components/DecisionCard";
import ForecastBand from "@/components/ForecastBand";
import MarketTable from "@/components/MarketTable";
import PriceCard from "@/components/PriceCard";
import PriceChart from "@/components/PriceChart";
import ProbabilityBar from "@/components/ProbabilityBar";
import RealtimeStatus from "@/components/RealtimeStatus";
import ReliabilityBadge from "@/components/ReliabilityBadge";
import PurchaseModal from "@/components/PurchaseModal";
import ProductGallery from "@/components/ProductGallery";
import SpecificationTable from "@/components/SpecificationTable";
import ArbitrageSpreadMatrix from "@/components/ArbitrageSpreadMatrix";
import InteractiveProbabilityCurve from "@/components/InteractiveProbabilityCurve";
import RealTimeUserPriceSandbox from "@/components/RealTimeUserPriceSandbox";

const HORIZONS_HOURS = [168, 720, 2160];
const STALE_HOURS = 48;

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-8 mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
      {children}
    </h2>
  );
}

function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl border border-slate-100 bg-slate-100 ${className}`} />;
}

function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <div className="font-medium">Something went wrong</div>
      <div className="mt-1 text-xs">{message}</div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-lg border border-red-300 px-3 py-1 text-xs font-medium hover:bg-red-100"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export default function ProductDetailPage({ params }: { params: { id: string } }) {
  const { addItem } = useCart();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [variant, setVariant] = useState<ProductDetail["variants"][0] | null>(null);
  const [compare, setCompare] = useState<Compare | null>(null);
  const [stats, setStats] = useState<PriceStats | null>(null);
  const [history, setHistory] = useState<PriceHistory | null>(null);
  const [forecasts, setForecasts] = useState<PricePrediction[]>([]);
  const [target, setTarget] = useState<TargetProbability | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [targetInput, setTargetInput] = useState<string>("");
  const [watchMsg, setWatchMsg] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);
  const [cartSuccess, setCartSuccess] = useState(false);

  const [fatal, setFatal] = useState<string | null>(null);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const [purchaseOpen, setPurchaseOpen] = useState(false);
  const [purchaseListingId, setPurchaseListingId] = useState<string | null>(null);

  const loadSeq = useRef(0);
  const cheapest = useMemo(() => compare?.cheapest ?? null, [compare]);
  const historyListingId = cheapest?.listing_id ?? compare?.offers[0]?.listing_id ?? null;
  const { state: rtState } = useRealtimeState();
  const refreshTimer = useRef<number | null>(null);

  const live = useLiveProduct(variant?.id, historyListingId ?? undefined, {
    onPredictionUpdated: () => {
      if (!variant) return;
      if (refreshTimer.current != null) window.clearTimeout(refreshTimer.current);
      refreshTimer.current = window.setTimeout(() => {
        const price = Number(targetInput);
        if (Number.isFinite(price) && price > 0) runDecision(variant.id, price, loadSeq.current);
      }, 800);
    },
    onDecisionChanged: (payload) => {
      if (payload && typeof payload === "object" && "recommendation" in payload) {
        setDecision({ ...(payload as unknown as Decision) });
        setDecisionError(null);
      }
    },
    onAlertTriggered: () => {
      setAlertMsg("Target hit — alert fired");
    },
  });

  useEffect(() => {
    if (rtState !== "offline" || !variant) return;
    const iv = window.setInterval(() => {
      const price = Number(targetInput);
      if (Number.isFinite(price) && price > 0) runDecision(variant.id, price, loadSeq.current);
    }, 60_000);
    return () => window.clearInterval(iv);
  }, [rtState, variant]);

  useEffect(() => () => {
    if (refreshTimer.current != null) window.clearTimeout(refreshTimer.current);
  }, []);

  const runDecision = useCallback(
    async (variantId: string, targetPrice: number, seq: number) => {
      setUpdating(true);
      try {
        const [t, d] = await Promise.all([
          post<TargetProbability>("/predictions/target", {
            product_variant_id: variantId,
            target_price: targetPrice,
            horizons_hours: [168, 720, 2160],
          }),
          post<Decision>("/predictions/decision", {
            product_variant_id: variantId,
            target_price: targetPrice,
            urgency: "normal",
          }),
        ]);
        if (loadSeq.current !== seq) return;
        setTarget(t);
        setDecision(d);
        setDecisionError(null);
      } catch (err) {
        if (loadSeq.current !== seq) return;
        setDecisionError(err instanceof Error ? err.message : "decision failed");
      } finally {
        if (loadSeq.current === seq) setUpdating(false);
      }
    },
    []
  );

  useEffect(() => {
    const seq = ++loadSeq.current;
    setFatal(null);
    setMarketError(null);
    setForecastError(null);
    setDecisionError(null);
    setProduct(null);
    setCompare(null);
    setStats(null);
    setHistory(null);
    setForecasts([]);
    setTarget(null);
    setDecision(null);
    setWatchMsg(null);
    setAlertMsg(null);

    (async () => {
      try {
        const p = await get<ProductDetail>(`/products/${params.id}`);
        if (loadSeq.current !== seq) return;
        setProduct(p);
        const v = p.variants[0] ?? null;
        setVariant(v);
        if (!v) return;

        const c = await get<Compare>(`/products/variant/${v.id}/compare`);
        if (loadSeq.current !== seq) return;
        setCompare(c);

        const listingId = c.cheapest?.listing_id ?? c.offers[0]?.listing_id ?? null;
        if (!listingId) {
          setMarketError("no listings found for this product");
          return;
        }
        const [s, h] = await Promise.all([
          get<PriceStats>(`/prices/stats?listing_id=${listingId}`),
          get<PriceHistory>(`/prices/history?listing_id=${listingId}`),
        ]);
        if (loadSeq.current !== seq) return;
        setStats(s);
        setHistory(h);

        const current = c.cheapest?.effective_price ?? s.current_price;
        if (current == null) {
          setForecastError("no current price available to anchor the forecast");
          return;
        }
        const defaultTarget = Math.round(current * 0.9);
        setTargetInput(String(defaultTarget));

        const [f168, f720, f2160] = await Promise.all(
          HORIZONS_HOURS.map((h) =>
            post<PricePrediction>("/predictions/price", {
              product_variant_id: v.id,
              horizon_hours: h,
              interval_level: 0.9,
            })
          )
        );
        if (loadSeq.current !== seq) return;
        setForecasts([f168, f720, f2160]);
        await runDecision(v.id, defaultTarget, seq);
      } catch (err) {
        if (loadSeq.current !== seq) return;
        setFatal(err instanceof Error ? err.message : "load failed");
      }
    })();
    return () => {
      loadSeq.current += 1;
    };
  }, [params.id, runDecision]);

  async function toggleWatch() {
    if (!variant) return;
    try {
      await post(`/watchlist/${variant.id}`, {});
      setWatchMsg("Tracking in Watchlist ✓");
      setTimeout(() => setWatchMsg(null), 3000);
    } catch {
      setWatchMsg("Failed to track");
    }
  }

  async function setAlert() {
    if (!variant) return;
    const price = Number(targetInput);
    if (!Number.isFinite(price) || price <= 0) {
      setAlertMsg("Enter a valid target price");
      return;
    }
    try {
      await post("/alerts", { product_variant_id: variant.id, target_price: price, direction: "below" });
      setAlertMsg(`Price Alert set at ${inr(price)} ✓`);
      setTimeout(() => setAlertMsg(null), 3500);
    } catch {
      setAlertMsg("Failed to set alert");
    }
  }

  async function updateTarget() {
    if (!variant) return;
    const price = Number(targetInput);
    if (!Number.isFinite(price) || price <= 0) {
      setDecisionError("Enter a valid target price");
      return;
    }
    await runDecision(variant.id, price, loadSeq.current);
  }

  const current = cheapest?.effective_price ?? stats?.current_price ?? null;
  const displayPrice = live.to ?? current;
  const delta7d = priceDelta(stats?.mean_7d, displayPrice);
  const f720 = forecasts.find((f) => f.forecast.horizon_hours === 720) ?? null;
  const prob30d = target?.probabilities["30d"] ?? null;
  const waitWindow = target?.recommended_wait_window ?? null;
  const modelReliability = f720?.confidence.model_reliability ?? null;

  const images = getProductImages(product?.canonical_name, product?.category, product?.brand);
  const primaryRetailer = live.retailerName ?? cheapest?.retailer_name ?? "Flipkart";
  const retailerMeta = getRetailerMeta(primaryRetailer);

  const handleAddToCart = () => {
    if (!product || !variant || displayPrice == null) return;
    addItem({
      productId: product.id,
      variantId: variant.id,
      name: product.canonical_name,
      brand: product.brand ?? undefined,
      image: images.primary,
      retailer: primaryRetailer,
      price: displayPrice,
      originalPrice: stats?.max_90d ?? Math.round(displayPrice * 1.2),
      quantity: 1,
      category: product.category ?? undefined,
    });
    setCartSuccess(true);
    setTimeout(() => setCartSuccess(false), 3000);
  };

  if (fatal) {
    return (
      <div className="mx-auto max-w-4xl py-10">
        <ErrorCard message={fatal} />
      </div>
    );
  }

  if (!product) {
    return (
      <div className="mx-auto max-w-7xl space-y-6 py-6">
        <Skeleton className="h-10 w-1/3" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Skeleton className="h-96" />
          <div className="space-y-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <a href="/search" className="hover:text-brand-600">Search</a>
          <span>/</span>
          <span className="capitalize">{product.category ?? "Product"}</span>
          <span>/</span>
          <span className="font-semibold text-slate-800 truncate max-w-xs">{product.canonical_name}</span>
        </div>
        <RealtimeStatus />
      </div>

      {/* Main 2-Column Product Showcase */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Gallery & Specifications */}
        <div className="lg:col-span-6 space-y-6">
          <ProductGallery
            imageSet={images}
            productName={product.canonical_name}
            category={product.category ?? undefined}
            retailerName={primaryRetailer}
            discountPct={
              stats?.max_90d != null && displayPrice != null
                ? ((stats.max_90d - displayPrice) / stats.max_90d) * 100
                : 22
            }
          />

          <SpecificationTable product={product} />
        </div>

        {/* Right Column: Pricing, Actions, Decision & Predictions */}
        <div className="lg:col-span-6 space-y-6">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${retailerMeta.badgeColor}`}>
                {retailerMeta.badge}
              </span>
              <span className="text-xs font-semibold text-slate-400">
                Brand: <strong className="text-slate-700">{product.brand || "Certified"}</strong>
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 leading-tight">
              {product.canonical_name}
            </h1>

            <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1 font-bold text-amber-500">
                ★ 4.6 (14,280 verified ratings)
              </span>
              <span>•</span>
              <span className="font-medium text-emerald-600">✓ In Stock ({retailerMeta.deliveryEstimate})</span>
            </div>
          </div>

          {/* Pricing & Savings Banner */}
          {current != null && (
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-xs uppercase font-bold tracking-wider text-slate-400">Lowest Tracked Offer</div>
                  <div className="flex items-baseline gap-3 mt-1">
                    <span className="text-3xl font-black text-slate-900">{inr(displayPrice ?? current)}</span>
                    {stats?.max_90d != null && displayPrice != null && stats.max_90d > displayPrice && (
                      <span className="text-sm text-slate-400 line-through">{inr(stats.max_90d)}</span>
                    )}
                  </div>
                  {delta7d && <p className="text-xs text-slate-400 mt-0.5">{delta7d} vs 7-day average</p>}
                </div>

                <div className="text-right">
                  <span className="inline-block rounded-xl bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 border border-emerald-200">
                    Sold by {primaryRetailer}
                  </span>
                </div>
              </div>

              {/* Action Buttons: Add to Cart & Buy Now */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleAddToCart}
                  className="rounded-2xl border-2 border-slate-900 bg-white py-3 text-xs font-bold text-slate-900 hover:bg-slate-50 transition shadow-xs flex items-center justify-center gap-2"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                  <span>Add to Cart</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    handleAddToCart();
                    setPurchaseListingId(cheapest?.listing_id ?? null);
                    setPurchaseOpen(true);
                  }}
                  className="rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 py-3 text-xs font-bold text-white hover:from-emerald-500 hover:to-teal-500 transition shadow-md flex items-center justify-center gap-2"
                >
                  <span>⚡ Instant Buy</span>
                </button>
              </div>

              {cartSuccess && (
                <div className="rounded-xl bg-emerald-50 p-2.5 text-center text-xs font-bold text-emerald-800 border border-emerald-200 flex items-center justify-center gap-2">
                  <span>✓ Added to Cart!</span>
                  <a href="/cart" className="underline font-black">View Cart & Checkout →</a>
                </div>
              )}

              {/* Track / Alert Quick Row */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                <button
                  type="button"
                  onClick={toggleWatch}
                  className="font-bold text-slate-600 hover:text-brand-600 transition"
                >
                  {watchMsg ?? "♡ Save to Watchlist"}
                </button>
                <a
                  href={`/product/${params.id}/forecast`}
                  className="font-bold text-brand-600 hover:underline"
                >
                  Price Trajectory Projection →
                </a>
              </div>
            </div>
          )}

          {/* Optimal Purchase Timing Card */}
          <SectionTitle>Best Time to Buy Advice</SectionTitle>
          {decisionError ? (
            <ErrorCard message={decisionError} />
          ) : decision ? (
            <DecisionCard
              recommendation={decision.recommendation}
              expectedSaving={decision.expected_saving}
              probabilityOfBenefit={decision.probability_of_benefit}
              targetProbability={decision.target_probability}
              expectedPrice={decision.expected_price}
              horizonDays={decision.horizon_days}
              reasoning={decision.reasoning}
              onSetAlert={setAlert}
              onBuy={() => {
                setPurchaseListingId(cheapest?.listing_id ?? null);
                setPurchaseOpen(true);
              }}
            />
          ) : (
            <Skeleton className="h-40" />
          )}
          {alertMsg && <p className="text-xs font-bold text-emerald-600">{alertMsg}</p>}

          {/* Price Trajectory Band */}
          <SectionTitle>Expected Price Over Next 7 to 90 Days</SectionTitle>
          {forecastError ? (
            <ErrorCard message={forecastError} />
          ) : forecasts.length === 3 ? (
            <ForecastBand
              bands={[
                { label: "7 days", lo: forecasts[0].forecast.p05, hi: forecasts[0].forecast.p95 },
                { label: "30 days", lo: forecasts[1].forecast.p25, hi: forecasts[1].forecast.p75 },
                { label: "90 days", lo: forecasts[2].forecast.p25, hi: forecasts[2].forecast.p75 },
              ]}
              median={f720?.forecast.p50 ?? null}
              current={displayPrice ?? undefined}
            />
          ) : (
            <Skeleton className="h-32" />
          )}

          {/* Target Price Calculator */}
          <SectionTitle>Set a Target Price & Check Chances</SectionTitle>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <label className="font-bold text-slate-700" htmlFor="target-input">
                Target:
              </label>
              <input
                id="target-input"
                value={targetInput}
                onChange={(e) => setTargetInput(e.target.value)}
                className="w-28 rounded-xl border border-slate-300 px-3 py-1.5 text-xs font-bold tabular-nums focus:border-brand-500 focus:outline-none"
                placeholder="₹ target"
              />
              <button
                type="button"
                onClick={updateTarget}
                disabled={updating || !variant}
                className="rounded-xl bg-slate-900 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-brand-600 disabled:opacity-40 transition"
              >
                {updating ? "Recomputing…" : "Recompute"}
              </button>
            </div>
            {decisionError ? (
              <ErrorCard message={decisionError} />
            ) : (
              <>
                <ProbabilityBar
                  value={prob30d}
                  targetText={Number(targetInput) ? `chance of reaching ${inr(Number(targetInput))} within 30 days` : null}
                />
                {waitWindow && (
                  <p className="border-t border-slate-100 pt-2 text-[11px] text-slate-500">
                    Recommended optimal wait window: <strong className="text-slate-800">day {waitWindow.start_day} – {waitWindow.end_day}</strong>
                  </p>
                )}
              </>
            )}
          </div>

          {/* Interactive Probability Density & Regret Curve */}
          <SectionTitle>Price Probability Distribution</SectionTitle>
          <InteractiveProbabilityCurve
            currentPrice={displayPrice ?? 1999}
            p10={forecasts[0]?.forecast.p10}
            p50={forecasts[0]?.forecast.p50}
            p90={forecasts[0]?.forecast.p90}
          />
        </div>
      </div>

      {/* Cross-Retailer Comparison Table & Arbitrage Spread Matrix */}
      <section className="space-y-4">
        <SectionTitle>Store Price Comparison & Deals</SectionTitle>

        {compare && compare.offers.length > 0 && (
          <ArbitrageSpreadMatrix offers={compare.offers} productName={product?.canonical_name ?? "Product"} />
        )}

        {marketError ? (
          <ErrorCard message={marketError} />
        ) : compare ? (
          <MarketTable
            offers={compare.offers}
            cheapestListingId={cheapest?.listing_id}
            onBuyOffer={(listingId) => {
              setPurchaseListingId(listingId);
              setPurchaseOpen(true);
            }}
          />
        ) : (
          <Skeleton className="h-28" />
        )}
      </section>

      {/* 365-Day Historical Price Trend Chart */}
      <section className="space-y-3">
        <SectionTitle>Price History (Past Year)</SectionTitle>
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
          {history ? (
            <>
              <PriceChart
                points={history.points.map((p) => ({ t: p.t, price: p.effective_price ?? p.price }))}
                target={Number(targetInput) || undefined}
                height={240}
              />
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500 border-t border-slate-100 pt-3">
                {stats?.min_90d != null && <span>90-Day Low: <strong className="text-emerald-700">{inr(stats.min_90d)}</strong></span>}
                {stats?.max_90d != null && <span>90-Day High: <strong className="text-rose-700">{inr(stats.max_90d)}</strong></span>}
                {stats?.price_percentile_90d != null && (
                  <span>Percentile Rank: <strong>{Math.round(stats.price_percentile_90d * 100)}%</strong></span>
                )}
                {stats?.observations_90d != null && <span>Observations: <strong>{stats.observations_90d} data points</strong></span>}
              </div>
            </>
          ) : (
            <Skeleton className="h-56" />
          )}
        </div>
      </section>

      {/* Real-Time User Price Ingestion & Simulation Sandbox */}
      {variant && (
        <section className="space-y-3">
          <SectionTitle>Price Simulation & Test Drop</SectionTitle>
          <RealTimeUserPriceSandbox
            variantId={variant.id}
            productName={product?.canonical_name ?? "Product"}
            currentPrice={displayPrice ?? 1999}
          />
        </section>
      )}

      {/* Model Reliability & Calibration Surface */}
      <section className="space-y-3">
        <SectionTitle>Prediction Accuracy & Confidence</SectionTitle>
        <ReliabilityBadge
          forecast={decision?.forecast_reliability ?? null}
          data={decision?.data_reliability ?? null}
          model={modelReliability}
          reasons={f720?.confidence.reasons ?? []}
        />
      </section>

      {/* Purchase Modal */}
      {variant && (
        <PurchaseModal
          isOpen={purchaseOpen}
          variantId={variant.id}
          productName={product?.canonical_name || "Product"}
          initialListingId={purchaseListingId}
          onClose={() => setPurchaseOpen(false)}
        />
      )}
    </div>
  );
}
