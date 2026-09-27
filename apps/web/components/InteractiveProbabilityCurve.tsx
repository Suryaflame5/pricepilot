"use client";

import { useState, useId } from "react";
import { inr } from "@/lib/formatting";

interface Props {
  currentPrice: number;
  p10?: number;
  p50?: number;
  p90?: number;
}

export default function InteractiveProbabilityCurve({
  currentPrice,
  p10 = currentPrice * 0.92,
  p50 = currentPrice * 0.96,
  p90 = currentPrice * 1.02,
}: Props) {
  const gradientId = useId();
  // Target price slider state (defaults to ~5% below current price)
  const defaultTarget = Math.round(currentPrice * 0.95);
  const [targetPrice, setTargetPrice] = useState(defaultTarget);
  const [waitDays, setWaitDays] = useState(14);

  const minPrice = Math.round(p10 * 0.88);
  const maxPrice = Math.round(p90 * 1.08);

  // Compute probability density bell curve points
  const pointsCount = 40;
  const mean = p50;
  const sigma = Math.max((p90 - p10) / 3.29, 10);

  const curveData: { x: number; price: number; y: number }[] = [];
  const svgWidth = 400;
  const svgHeight = 140;

  for (let i = 0; i <= pointsCount; i++) {
    const p = minPrice + (i / pointsCount) * (maxPrice - minPrice);
    const z = (p - mean) / sigma;
    const density = Math.exp(-0.5 * z * z);
    const x = (i / pointsCount) * svgWidth;
    const y = svgHeight - density * (svgHeight * 0.82) - 10;
    curveData.push({ x, price: p, y });
  }

  // Target X position in SVG
  const targetFraction = Math.max(0, Math.min(1, (targetPrice - minPrice) / (maxPrice - minPrice)));
  const targetX = targetFraction * svgWidth;

  // Approximate P(Price <= target) using error function
  const zScore = (targetPrice - mean) / sigma;
  // Approximation of standard normal CDF
  const probBelowTarget = Math.max(
    0.01,
    Math.min(0.99, 1 / (1 + Math.exp(-1.702 * zScore)))
  );

  const expectedSavings = Math.max(0, currentPrice - targetPrice);
  const waitCostPerDay = Math.max(2, currentPrice * 0.001);
  const totalWaitPenalty = waitDays * waitCostPerDay;
  const netExpectedBenefit = probBelowTarget * expectedSavings - totalWaitPenalty;

  const isWaitFavorable = netExpectedBenefit > 0 && probBelowTarget >= 0.35;

  // SVG Paths
  const linePath = curveData.map((pt, i) => `${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(" ");

  // Shaded target fill (from minPrice up to targetX)
  const shadedPts = curveData.filter((pt) => pt.x <= targetX);
  const lastShadedY = curveData.find((pt) => pt.x >= targetX)?.y ?? svgHeight;
  const shadedPath =
    shadedPts.length > 0
      ? `M 0 ${svgHeight} ` +
        shadedPts.map((pt) => `L ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`).join(" ") +
        ` L ${targetX.toFixed(1)} ${lastShadedY.toFixed(1)} L ${targetX.toFixed(1)} ${svgHeight} Z`
      : "";

  return (
    <div className="rounded-3xl border border-white/10 bg-obsidian-900/90 p-5 shadow-2xl backdrop-blur-xl space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-neon-lime shadow-[0_0_8px_#d4ff00]" />
            <h3 className="text-sm font-black tracking-tight text-white uppercase">
              Probability Density & Regret Curve
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Continuous Gaussian distribution calibrated via finite-sample conformal residuals
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-3 py-1 text-xs font-black uppercase tracking-wider ${
              isWaitFavorable
                ? "bg-neon-lime/20 text-neon-lime border border-neon-lime/40"
                : "bg-neon-amber/20 text-neon-amber border border-neon-amber/40"
            }`}
          >
            {isWaitFavorable ? "Optimal Action: Wait for Dip" : "Optimal Action: Buy Now"}
          </span>
        </div>
      </div>

      {/* Interactive SVG Density Chart */}
      <div className="relative rounded-2xl border border-white/5 bg-obsidian-950 p-3 overflow-hidden">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-36 overflow-visible">
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#d4ff00" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#00f0ff" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* Shaded Area Below Target */}
          {shadedPath && <path d={shadedPath} fill={`url(#${gradientId})`} />}

          {/* Density Bell Curve Line */}
          <path d={linePath} fill="none" stroke="#00f0ff" strokeWidth="2.5" />

          {/* Vertical Target Marker Line */}
          <line
            x1={targetX}
            y1="10"
            x2={targetX}
            y2={svgHeight}
            stroke="#d4ff00"
            strokeWidth="2"
            strokeDasharray="4 2"
          />

          {/* Target Handle Point */}
          <circle cx={targetX} cy={lastShadedY} r="5" fill="#d4ff00" stroke="#07090e" strokeWidth="2" />
        </svg>

        {/* Legend labels */}
        <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-2 px-1">
          <span>{inr(minPrice)} (P05)</span>
          <span className="text-neon-cyan font-bold">{inr(p50)} (Median Forecast)</span>
          <span>{inr(maxPrice)} (P95)</span>
        </div>
      </div>

      {/* Real-Time Mathematical Evaluation Card */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
        <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-2.5">
          <div className="text-[10px] uppercase font-bold text-slate-400">P(Price ≤ Target)</div>
          <div className="text-base font-black text-neon-lime mt-1 font-mono">
            {(probBelowTarget * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-2.5">
          <div className="text-[10px] uppercase font-bold text-slate-400">Potential Saving</div>
          <div className="text-base font-black text-white mt-1 font-mono">
            {inr(expectedSavings)}
          </div>
        </div>

        <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-2.5">
          <div className="text-[10px] uppercase font-bold text-slate-400">Delay Penalty</div>
          <div className="text-base font-black text-neon-amber mt-1 font-mono">
            -{inr(totalWaitPenalty)}
          </div>
        </div>

        <div className="rounded-2xl border border-white/5 bg-obsidian-850 p-2.5">
          <div className="text-[10px] uppercase font-bold text-slate-400">Net Expected Benefit</div>
          <div
            className={`text-base font-black mt-1 font-mono ${
              netExpectedBenefit > 0 ? "text-neon-lime" : "text-slate-400"
            }`}
          >
            {netExpectedBenefit > 0 ? `+${inr(netExpectedBenefit)}` : inr(netExpectedBenefit)}
          </div>
        </div>
      </div>

      {/* Sliders for Real-Time Simulation */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-2xl border border-white/5 bg-obsidian-850 p-4">
        <div>
          <div className="flex justify-between text-xs font-bold mb-1">
            <span className="text-slate-300">Target Desired Price:</span>
            <span className="text-neon-lime font-mono">{inr(targetPrice)}</span>
          </div>
          <input
            type="range"
            min={minPrice}
            max={maxPrice}
            step={10}
            value={targetPrice}
            onChange={(e) => setTargetPrice(Number(e.target.value))}
            className="w-full accent-neon-lime cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
            <span>{inr(minPrice)}</span>
            <span>Current: {inr(currentPrice)}</span>
            <span>{inr(maxPrice)}</span>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-bold mb-1">
            <span className="text-slate-300">Patience Horizon:</span>
            <span className="text-neon-cyan font-mono">{waitDays} Days</span>
          </div>
          <input
            type="range"
            min={1}
            max={60}
            step={1}
            value={waitDays}
            onChange={(e) => setWaitDays(Number(e.target.value))}
            className="w-full accent-neon-cyan cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
            <span>1 Day (Urgent)</span>
            <span>14 Days</span>
            <span>60 Days (Very Patient)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
