"""Prediction API schemas (blueprint sections 21-23)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PricePredictionRequest(BaseModel):
    product_variant_id: uuid.UUID
    horizon_hours: int = Field(default=24 * 30, ge=1, le=24 * 365)
    interval_level: float = Field(default=0.9, ge=0.5, le=0.99)


class QuantileForecast(BaseModel):
    horizon_hours: int
    p05: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float


class ModelForecastOut(BaseModel):
    model: str
    point: float
    weight: float


class ReliabilityOut(BaseModel):
    historical_coverage: float | None = None
    calibration_error: float | None = None
    historical_mae: float | None = None
    backtest_horizons: int | None = None
    samples: int | None = None


class ConfidenceOut(BaseModel):
    score: float
    level: str  # HIGH | MEDIUM | LOW | INSUFFICIENT
    reasons: list[str]
    # V1.1: three independently-measured components + decision weight function
    forecast_confidence: float | None = None
    model_reliability: float | None = None
    data_reliability: float | None = None
    components: dict | None = None
    weights: dict | None = None


class PricePredictionResponse(BaseModel):
    variant_id: uuid.UUID
    generated_at: datetime
    current_price: float | None
    forecast: QuantileForecast
    interval: dict  # {"level": 0.9, "lower": ..., "upper": ...}
    probability_below_target: float | None = None
    target_price: float | None = None
    per_model: list[ModelForecastOut] = []
    disagreement: float | None = None
    confidence: ConfidenceOut
    reliability: ReliabilityOut
    model_version: str
    warnings: list[str] = []
    calibration_key_used: str | None = None
    conformal_bucket_used: str | None = None


class TargetProbabilityRequest(BaseModel):
    product_variant_id: uuid.UUID
    target_price: float
    horizons_hours: list[int] = Field(default=[24, 24 * 7, 24 * 14, 24 * 30, 24 * 60, 24 * 90])


class TargetProbabilityResponse(BaseModel):
    variant_id: uuid.UUID
    target_price: float
    current_price: float | None
    probabilities: dict[str, float]  # horizon_label -> calibrated probability
    recommended_wait_window: dict[str, int] | None = None
    confidence: ConfidenceOut


class DecisionRequest(BaseModel):
    product_variant_id: uuid.UUID
    target_price: float | None = None
    max_wait_days: int | None = Field(default=None, ge=0)
    urgency: str = Field(default="normal")  # normal | high


class DecisionOut(BaseModel):
    recommendation: str  # BUY_NOW | WAIT | INSUFFICIENT_CONFIDENCE
    expected_saving: float | None = None
    probability_of_benefit: float | None = None
    reasoning: list[str]
    # V1.2: machine-readable decision contract (LLM verbalizes, never recomputes)
    current_price: float | None = None
    expected_price: float | None = None
    target: float | None = None
    target_probability: float | None = None
    forecast_reliability: float | None = None
    data_reliability: float | None = None
    horizon_days: int | None = None
    reason_codes: list[str] = []
