export interface Product {
  id: string;
  brand: string | null;
  model: string | null;
  canonical_name: string;
  category: string | null;
  subcategory: string | null;
  description: string | null;
  launched_at: string | null;
  image?: string | null;
  price?: number;
  mrp?: number;
  retailer?: string;
  store_count?: number;
}

export interface Variant {
  id: string;
  variant_name: string | null;
  color: string | null;
  storage: string | null;
  size: string | null;
  condition: string | null;
  gtin: string | null;
  sku: string | null;
}

export interface ProductDetail extends Product {
  variants: Variant[];
}

export interface RetailerOffer {
  listing_id: string;
  retailer_name: string;
  current_price: number;
  effective_price: number;
  url: string | null;
  availability: string | null;
  observed_at: string | null;
}

export interface Compare {
  variant_id: string;
  product_name: string;
  cheapest: RetailerOffer | null;
  offers: RetailerOffer[];
}

export interface PricePoint {
  t: string;
  price: number;
  effective_price: number | null;
}

export interface PriceHistory {
  listing_id: string;
  variant_id: string;
  points: PricePoint[];
}

export interface PriceStats {
  listing_id: string;
  current_price: number | null;
  mean_7d: number | null;
  mean_30d: number | null;
  mean_90d: number | null;
  min_7d: number | null;
  min_30d: number | null;
  min_90d: number | null;
  max_7d: number | null;
  max_30d: number | null;
  max_90d: number | null;
  price_percentile_90d: number | null;
  observations_90d: number;
}

export interface QuantileForecast {
  horizon_hours: number;
  p05: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
}

export interface ModelForecast {
  model: string;
  point: number;
  weight: number;
}

export interface Confidence {
  score: number;
  level: "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT";
  reasons: string[];
  forecast_confidence?: number | null;
  model_reliability?: number | null;
  data_reliability?: number | null;
  components?: { forecast: number; model: number; data: number } | null;
  weights?: { forecast: number; model: number; data: number } | null;
}

export interface PricePrediction {
  variant_id: string;
  generated_at: string;
  current_price: number | null;
  forecast: QuantileForecast;
  interval: { level: number; lower: number; upper: number; qhat: number };
  probability_below_target: number | null;
  target_price: number | null;
  per_model: ModelForecast[];
  disagreement: number | null;
  confidence: Confidence;
  reliability: {
    historical_coverage: number | null;
    calibration_error: number | null;
    historical_mae: number | null;
    backtest_horizons: number | null;
    samples: number | null;
  };
  model_version: string;
  warnings: string[];
}

export interface TargetProbability {
  variant_id: string;
  target_price: number;
  current_price: number | null;
  probabilities: Record<string, number>;
  recommended_wait_window: { start_day: number; end_day: number } | null;
  confidence: Confidence;
}

export type Recommendation = "BUY_NOW" | "WAIT" | "INSUFFICIENT_CONFIDENCE";

export interface Decision {
  recommendation: Recommendation;
  expected_saving: number | null;
  probability_of_benefit: number | null;
  reasoning: string[];
  // V1.2 machine-readable decision contract (the narrator verbalizes it verbatim)
  current_price: number | null;
  expected_price: number | null;
  target: number | null;
  target_probability: number | null;
  forecast_reliability: number | null;
  data_reliability: number | null;
  horizon_days: number | null;
  reason_codes: string[];
}

export interface ChatStep {
  kind: string;
  summary: string;
  details: Record<string, unknown>;
}

export interface ChatResponse {
  reply: string;
  steps: ChatStep[];
  tool_calls: { tool: string; arguments: Record<string, unknown> }[];
}

export interface Alert {
  id: string;
  product_variant_id: string;
  target_price: number;
  direction: string;
  active: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface VariantWithProduct extends Variant {
  product: Product | null;
}

// Purchase workflow types
export type SessionStatus =
  | "SEARCHING"
  | "SELECTED"
  | "PRICE_VERIFIED"
  | "CHECKOUT_READY"
  | "USER_CONFIRMED"
  | "ORDER_PLACED"
  | "TRACKING"
  | "COMPLETED";

export interface ShoppingSession {
  id: string;
  product_variant_id: string;
  conversation_id: string | null;
  strategy: string;
  status: SessionStatus;
  selected_listing_id: string | null;
  selected_offer: Record<string, unknown>;
  checkout_total: number | null;
  delivery_estimate: string | null;
  created_at: string;
  expires_at: string;
}

export interface ShoppingSessionWithOffers extends ShoppingSession {
  offers: Array<{
    listing_id: string;
    retailer_name: string;
    effective_price: number;
    delivery_days?: number | null;
  }>;
}

export interface PriceVerification {
  status: string;
  price_changed: boolean;
  previous_effective_price: number | null;
  current_effective_price: number | null;
  checkout_total: number | null;
}

export interface CheckoutReady {
  status: string;
  checkout_total: number | null;
  delivery_estimate: string | null;
  offer: Record<string, unknown>;
}

export interface OrderPlaced {
  status: string;
  order_ref: string | null;
  provider: string | null;
  retailer_name: string | null;
  total: number | null;
  tracking_url: string | null;
}

export interface OrderStatus {
  status: string;
  order_ref: string | null;
  provider: string | null;
  retailer_name: string | null;
  detail: string | null;
  tracking_url: string | null;
}

// Monitoring & Reliability types
export interface RegistryEntry {
  model_id: string;
  name: string;
  status: "EXPERIMENT" | "CANDIDATE" | "SHADOW" | "CHAMPION" | "RETIRED";
  model_type: string;
  category: string | null;
  horizon_hours: number | null;
  metrics: Record<string, number>;
  promoted_at: string | null;
  retired_at: string | null;
}

export interface CalibrationCurve {
  key: string;
  n_pairs: number | null;
  ece: number | null;
}

export interface CalibrationSummary {
  curves: CalibrationCurve[];
}

export interface CoverageMetric {
  target_level: number;
  empirical_coverage: number;
  coverage_error: number;
  n: number;
  acceptable: boolean;
}

export interface LedgerRow {
  category: string;
  horizon_days: number;
  n: number;
  coverage_90: number | null;
  mae: number | null;
  median_error: number | null;
  brier: number | null;
  model_version: string | null;
}

export interface LedgerData {
  rows: LedgerRow[];
  total_predictions: number;
  outcomes_recorded: number;
}

export interface AdminTrace {
  id: string;
  conversation_id: string;
  turn_index: number;
  user_message: string;
  intent: string;
  backend: string;
  requires: string[];
  tool_calls: Array<{ tool: string; arguments: Record<string, unknown>; ok: boolean; duration_ms: number }>;
  reply: string;
  error: string | null;
  created_at: string;
}

export interface AdminTracePage {
  items: AdminTrace[];
  total: number;
  offset: number;
  limit: number;
}
