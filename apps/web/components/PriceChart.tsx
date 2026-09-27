"use client";

import { useMemo } from "react";

interface Props {
  points: { t: string; price: number }[];
  target?: number;
  height?: number;
}

export default function PriceChart({ points, target, height = 200 }: Props) {
  const { width, path, targetY, min, max, lastY } = useMemo(() => {
    const w = 640;
    const pad = 8;
    if (points.length < 2) return { width: w, path: "", targetY: null, min: 0, max: 0, lastY: 0 };
    const prices = points.map((p) => p.price);
    const lo = Math.min(...prices, target ?? Infinity);
    const hi = Math.max(...prices, target ?? -Infinity);
    const span = hi - lo || 1;
    const step = (w - pad * 2) / (points.length - 1);
    const y = (v: number) => pad + (1 - (v - lo) / span) * (height - pad * 2);
    const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${pad + i * step},${y(p.price)}`).join(" ");
    return {
      width: w,
      path: d,
      targetY: target == null ? null : y(target),
      min: lo,
      max: hi,
      lastY: y(prices[prices.length - 1]),
    };
  }, [points, target, height]);

  if (points.length < 2) {
    return <div className="text-sm text-slate-400">Not enough history to render a chart.</div>;
  }

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="price history chart">
        <polyline points={path} fill="none" stroke="#4f46e5" strokeWidth="2" />
        {targetY != null && (
          <line
            x1={0}
            x2={width}
            y1={targetY}
            y2={targetY}
            stroke="#dc2626"
            strokeWidth="1.5"
            strokeDasharray="6 4"
          />
        )}
        <circle cx={width - 8} cy={lastY} r="3.5" fill="#4f46e5" />
      </svg>
      <div className="mt-1 flex justify-between text-xs text-slate-500">
        <span>min {min.toLocaleString("en-IN")}</span>
        {target != null && <span className="text-red-600">target {target.toLocaleString("en-IN")}</span>}
        <span>max {max.toLocaleString("en-IN")}</span>
      </div>
    </div>
  );
}
