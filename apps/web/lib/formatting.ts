// V2 formatting primitives — single source for how PricePilot renders numbers.
// PRIMARY (price/decision) renders big and rounded; SECONDARY (forecast)
// renders precise; TERTIARY (reliability) is monospace technical.

export function inr(v: number | null | undefined): string {
  if (v == null) return "n/a";
  return `₹${Math.round(v).toLocaleString("en-IN")}`;
}

export function inrPrecise(v: number | null | undefined): string {
  if (v == null) return "n/a";
  return `₹${v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function inrCompact(v: number | null | undefined): string {
  if (v == null) return "n/a";
  if (Math.abs(v) >= 1_00_00_000) return `₹${(v / 1_00_00_000).toFixed(1)}Cr`;
  if (Math.abs(v) >= 1_00_000) return `₹${(v / 1_00_000).toFixed(1)}L`;
  if (Math.abs(v) >= 1_000) return `₹${(v / 1_000).toFixed(1)}k`;
  return `₹${Math.round(v)}`;
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v == null) return "n/a";
  return `${(v * 100).toFixed(digits)}%`;
}

export function deltaPct(prev: number | null | undefined, curr: number | null | undefined): string | null {
  if (prev == null || curr == null || prev === 0) return null;
  const d = ((curr - prev) / prev) * 100;
  if (Math.abs(d) < 0.05) return null;
  return `${d < 0 ? "↓" : "↑"} ${Math.abs(d).toFixed(1)}%`;
}

export function priceDelta(prev: number | null | undefined, curr: number | null | undefined): string | null {
  if (prev == null || curr == null) return null;
  const d = curr - prev;
  if (Math.abs(d) < 0.005) return null;
  return `${d < 0 ? "↓" : "↑"} ₹${Math.abs(d).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export type Recommendation = "BUY_NOW" | "WAIT" | "INSUFFICIENT_CONFIDENCE";

export const RECO_LABEL: Record<Recommendation, string> = {
  BUY_NOW: "BUY NOW",
  WAIT: "WAIT",
  INSUFFICIENT_CONFIDENCE: "INSUFFICIENT CONFIDENCE",
};

export const RECO_STYLE: Record<Recommendation, string> = {
  BUY_NOW: "bg-emerald-100 text-emerald-800",
  WAIT: "bg-amber-100 text-amber-800",
  INSUFFICIENT_CONFIDENCE: "bg-red-100 text-red-800",
};
