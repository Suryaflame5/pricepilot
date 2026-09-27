"""Prediction engine orchestrator (blueprint sections 15-19, 21-26), V1.1.

Pipeline: history -> models -> ensemble -> probabilistic layer -> calibration
-> conformal interval -> confidence -> decision. The engine never fabricates
certainty: it reports calibrated probabilities and refuses strong claims when
the evidence (data quantity, freshness, agreement, historical accuracy,
calibration, volatility, regime stability) is insufficient.

V1.1 changes:
- Confidence is split into three independently-measured components:
      forecast_confidence  - how trustworthy THIS prediction is
      model_reliability    - how good this model has been historically
      data_reliability     - how trustworthy the input data is
  and decision_confidence = g(forecast, model, data) with documented weights.
- Conformal intervals are regime-conditional (wider under volatility = correct).
- Calibration uses hierarchical keys incl. regime + retailer (specific -> global).
- Serving is registry-aware: the champion's model_id is stamped on results and
  challengers can run in shadow.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prediction_engine.backtesting import BacktestResult, walk_forward_backtest
from prediction_engine.calibration import CalibrationStore
from prediction_engine.conformal import (
    RegimeConformalStore,
    conformal_quantile,
    interval as _conformal_interval,
)
from prediction_engine.ensemble import Ensemble
from prediction_engine.evaluation import brier_score
from prediction_engine.models.base import QUANTILES
from prediction_engine.models.baseline import (
    ExponentialSmoothingForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
)
from prediction_engine.models.gbm import fit_gbm_models
from prediction_engine.models.statistical import ARIMAForecaster
from prediction_engine.regime import classify_regime, detect_change_point
from prediction_engine.registry import ModelRegistry

logger = logging.getLogger(__name__)

MODEL_VERSION = "pricepilot-v1.1.0"
HORIZON_TO_DAYS = {24: 1, 24 * 7: 7, 24 * 14: 14, 24 * 30: 30, 24 * 60: 60, 24 * 90: 90}
GBM_MIN_SAMPLES = 60

# decision_confidence = g(forecast, model, data) - documented weights
CONFIDENCE_WEIGHTS = {"forecast": 0.40, "model": 0.35, "data": 0.25}


@dataclass
class ForecastResult:
    series_len: int
    current_price: float | None
    horizon: int
    quantiles: np.ndarray  # (horizon, n_quantiles)
    per_model: dict[str, float]
    weights: dict[str, float]
    disagreement: float
    backtest: BacktestResult
    regime: dict
    change_point: int | None
    interval: dict
    calibration_ece: float | None = None
    confidence: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    model_version: str = MODEL_VERSION
    calibration_key_used: str | None = None
    conformal_bucket_used: str | None = None

    def quantile_at(self, h: int) -> dict[float, float]:
        return {q: round(float(self.quantiles[h - 1, i]), 2) for i, q in enumerate(QUANTILES)}


def _prob_below_target(path_q: np.ndarray, target: float) -> float:
    """P(price <= target) by interpolation between forecast quantiles."""
    q = np.asarray(QUANTILES)
    if target >= path_q[-1]:
        return 1.0
    if target <= path_q[0]:
        return 0.0
    return float(np.interp(target, path_q, q))


class PredictionEngine:
    def __init__(
        self,
        registry_dir: str | Path | None = None,
        calibration_dir: str | Path | None = None,
        conformal_dir: str | Path | None = None,
        shadow_dir: str | Path | None = None,
    ) -> None:
        self.registry_dir = Path(registry_dir) if registry_dir else None
        self.calibration = CalibrationStore(calibration_dir)
        self.conformal = RegimeConformalStore(conformal_dir)
        self.conformal.load()
        self.registry = ModelRegistry(registry_dir)
        self.shadow = None
        if shadow_dir:
            from prediction_engine.shadow import ShadowRunner

            self.shadow = ShadowRunner(shadow_dir)
        self._weights: dict[str, float] | None = None
        self._model_cache: dict = {}
        self._backtest_cache: dict = {}
        self._load_weights()

    # ------------------------------------------------------------------ #
    # Registry
    # ------------------------------------------------------------------ #
    def _load_weights(self) -> None:
        if not self.registry_dir:
            return
        path = self.registry_dir / "ensemble_weights.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._weights = {k: float(v) for k, v in data.get("weights", {}).items()}
            except Exception as exc:
                logger.warning("failed to load ensemble weights: %s", exc)

    def save_weights(self, weights: dict[str, float]) -> None:
        if not self.registry_dir:
            return
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        (self.registry_dir / "ensemble_weights.json").write_text(
            json.dumps(
                {"weights": weights, "version": MODEL_VERSION, "updated_at": datetime.now(timezone.utc).isoformat()},
                indent=2,
            )
        )

    def serving_model_id(self, category: str | None = None) -> str:
        champion = self.registry.get_champion(category)
        return champion.model_id if champion else MODEL_VERSION

    # ------------------------------------------------------------------ #
    # Core forecast (synchronous, numpy only)
    # ------------------------------------------------------------------ #
    def _build_models(self, y: np.ndarray, horizon: int) -> list:
        models = [
            NaiveForecaster(),
            MovingAverageForecaster(window=7),
            ExponentialSmoothingForecaster(alpha=0.3),
            SeasonalNaiveForecaster(period=7),
            ARIMAForecaster(),
        ]
        if len(y) >= GBM_MIN_SAMPLES:
            from prediction_engine.models.gbm import fit_horizons

            models.append(fit_gbm_models(y, fit_horizons(horizon)))
        return models

    def _cached_models(self, y: np.ndarray, horizon: int) -> list:
        """Cache fitted model zoo by (len, first, last) - repeated requests
        for the same product skip the expensive ARIMA/GBM refits."""
        key = (len(y), round(float(y[0]), 2), round(float(y[-1]), 2), horizon)
        if key not in self._model_cache:
            if len(self._model_cache) > 16:
                self._model_cache.pop(next(iter(self._model_cache)))
            self._model_cache[key] = self._build_models(y, horizon)
        return self._model_cache[key]

    def _cached_backtest(
        self, y: np.ndarray, horizon: int, models: list, weights: dict[str, float] | None = None
    ) -> BacktestResult:
        """Cache walk-forward backtest by (len, first, last, horizon) to achieve sub-second inference."""
        key = (len(y), round(float(y[0]), 2), round(float(y[-1]), 2), horizon)
        if key not in self._backtest_cache:
            if len(self._backtest_cache) > 32:
                self._backtest_cache.pop(next(iter(self._backtest_cache)))
            self._backtest_cache[key] = walk_forward_backtest(y, horizon, models, weights=weights)
        return self._backtest_cache[key]

    def forecast_from_series(
        self,
        series: pd.Series,
        horizon: int,
        interval_level: float = 0.9,
        category: str | None = None,
        models: list | None = None,
        regime: str | None = None,
        retailer: str | None = None,
        match_confidence: float | None = None,
        quality_score: float | None = None,
        data_tier: str | None = None,
    ) -> ForecastResult:
        warnings: list[str] = []
        if series.empty:
            raise ValueError("no price history available for this product")

        y = series.dropna().to_numpy(dtype=float)
        if len(y) < 5:
            raise ValueError(f"insufficient history: {len(y)} observations")

        last_ts = series.index[-1]
        if getattr(last_ts, "tz", None) is None:
            last_ts = last_ts.tz_localize("utc")
        if last_ts < pd.Timestamp.utcnow() - pd.Timedelta(days=7):
            warnings.append("data is stale (last observation older than 7 days)")

        models = models or self._cached_models(y, horizon)
        weights = self._weights or {m.name: 1.0 / len(models) for m in models}
        ensemble = Ensemble(models, weights)
        path, points = ensemble.forecast(y, horizon, QUANTILES)

        backtest = self._cached_backtest(y, horizon, models, weights=weights)
        disagreement = ensemble.disagreement(points)

        change_point = detect_change_point(y)
        detected_regime = classify_regime(y, change_point)
        regime_label = regime or detected_regime.get("regime")

        residuals = backtest.residuals.get(1)
        if residuals is not None and len(residuals):
            qhat, bucket_used = self.conformal.qhat_for(1, regime_label, interval_level)
            if qhat <= 0:
                qhat = conformal_quantile(residuals, interval_level)
                bucket_used = "GLOBAL(fallback)"
        else:
            qhat = float(np.std(np.diff(y))) * 1.645 or float(y[-1]) * 0.02
            bucket_used = "heuristic"
            warnings.append("no backtest residuals yet; interval falls back to volatility estimate")
        lo, hi = _conformal_interval(float(path[0, QUANTILES.index(0.5)]), qhat)

        cal_ece = self._calibration_error(backtest)
        confidence = self._confidence(
            y, series, backtest, disagreement, detected_regime, float(y[-1]), horizon,
            match_confidence=match_confidence, quality_score=quality_score, data_tier=data_tier,
        )

        return ForecastResult(
            series_len=len(y),
            current_price=float(y[-1]),
            horizon=horizon,
            quantiles=path,
            per_model=points,
            weights=ensemble.weights,
            disagreement=round(disagreement, 2),
            backtest=backtest,
            regime=detected_regime,
            change_point=change_point,
            interval={"level": interval_level, "lower": lo, "upper": hi, "qhat": round(qhat, 2)},
            calibration_ece=cal_ece,
            confidence=confidence,
            warnings=warnings,
            model_version=self.serving_model_id(category),
            calibration_key_used=self.calibration.get_key(category, horizon),
            conformal_bucket_used=bucket_used,
        )

    def evaluate_with_user_point(
        self,
        series: pd.Series,
        user_price: float,
        horizon: int = 7,
        interval_level: float = 0.90,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Ingests a real-time user-observed price point, computes one-step update,
        evaluates model accuracy metrics before vs after, and measures conformal calibration."""
        from prediction_engine.evaluation import (
            directional_accuracy,
            empirical_coverage,
            mae,
            mape,
            rmse,
            smape,
            winkler_score,
        )

        base_res = self.forecast_from_series(
            series, horizon=horizon, interval_level=interval_level, category=category
        )
        base_p50 = float(base_res.quantiles[0, QUANTILES.index(0.5)])
        base_p10 = float(base_res.quantiles[0, QUANTILES.index(0.10)])
        base_p90 = float(base_res.quantiles[0, QUANTILES.index(0.90)])

        actual_arr = np.array([float(user_price)])
        pred_arr = np.array([base_p50])
        lo_arr = np.array([base_p10])
        hi_arr = np.array([base_p90])

        instant_error = float(user_price - base_p50)
        inside_conformal_bounds = bool(base_p10 <= user_price <= base_p90)
        winkler = winkler_score(actual_arr, lo_arr, hi_arr, alpha=1.0 - interval_level)

        # Extended series with user observation
        now_ts = pd.Timestamp.now(timezone.utc)
        if getattr(series.index, "tz", None) is None:
            now_ts = pd.Timestamp.now()
        extended_series = pd.concat([series, pd.Series([float(user_price)], index=[now_ts])])

        updated_res = self.forecast_from_series(
            extended_series, horizon=horizon, interval_level=interval_level, category=category
        )
        updated_p50 = float(updated_res.quantiles[0, QUANTILES.index(0.5)])
        updated_lo = float(updated_res.interval["lower"])
        updated_hi = float(updated_res.interval["upper"])

        target_h = str(horizon)
        if target_h not in updated_res.backtest.metrics:
            available = [int(k) for k in updated_res.backtest.metrics.keys() if k.isdigit()]
            target_h = str(max(available)) if available else "1"
        metrics = updated_res.backtest.metrics.get(target_h, {})

        return {
            "user_price": user_price,
            "previous_price": float(series.iloc[-1]),
            "base_p50_prediction": round(base_p50, 2),
            "updated_p50_prediction": round(updated_p50, 2),
            "instant_error": round(instant_error, 2),
            "instant_smape": round(float(smape(actual_arr, pred_arr)), 2),
            "instant_mape": round(float(mape(actual_arr, pred_arr)), 2),
            "inside_conformal_bounds": inside_conformal_bounds,
            "conformal_lower": round(updated_lo, 2),
            "conformal_upper": round(updated_hi, 2),
            "winkler_score": round(float(winkler), 2),
            "updated_weights": {k: round(v, 4) for k, v in updated_res.weights.items()},
            "per_model_predictions": {k: round(float(v), 2) for k, v in updated_res.per_model.items()},
            "backtest_metrics": metrics,
            "regime": updated_res.regime,
            "confidence_score": updated_res.confidence.get("score"),
            "confidence_level": updated_res.confidence.get("level"),
            "disagreement": updated_res.disagreement,
        }

    def _calibration_error(self, backtest: BacktestResult) -> float | None:
        from prediction_engine.calibration import expected_calibration_error

        if not backtest.prob_outcome:
            return None
        probs = np.asarray([p for p, _ in backtest.prob_outcome])
        outcomes = np.asarray([o for _, o in backtest.prob_outcome])
        return round(expected_calibration_error(probs, outcomes), 4)

    # ------------------------------------------------------------------ #
    # Three-part confidence
    # ------------------------------------------------------------------ #
    def _confidence(
        self,
        y: np.ndarray,
        series: pd.Series,
        backtest: BacktestResult,
        disagreement: float,
        regime: dict,
        current_price: float,
        horizon: int,
        match_confidence: float | None = None,
        quality_score: float | None = None,
        data_tier: str | None = None,
    ) -> dict:
        n = len(y)
        reasons: list[str] = []
        if n < 30:
            reasons.append(f"only {n} observations of history")

        last_ts = series.index[-1]
        if getattr(last_ts, "tz", None) is None:
            last_ts = last_ts.tz_localize("utc")
        age_hours = (pd.Timestamp.utcnow() - last_ts).total_seconds() / 3600
        if age_hours > 24 * 7:
            reasons.append("price data is stale")

        # ---- forecast_confidence: THIS prediction -----------------------
        quantity = min(1.0, np.log10(n) / 3.0)
        freshness = max(0.0, 1.0 - age_hours / (24 * 14))
        agreement = max(0.0, 1.0 - np.tanh(disagreement / current_price * 40))
        if disagreement / current_price > 0.05:
            reasons.append(f"high model disagreement ({disagreement:.0f} INR)")
        stability = 1.0 if regime.get("stable") else 0.4
        if not regime.get("stable"):
            reasons.append(f"regime: {regime.get('regime')} (unstable)")
        vol = float(y[-12:].std(ddof=1) / current_price) if len(y) >= 12 else 0.5
        volatility = max(0.0, 1.0 - np.tanh(vol * 25))

        forecast_confidence = (
            0.30 * quantity
            + 0.20 * freshness
            + 0.25 * agreement
            + 0.15 * stability
            + 0.10 * volatility
        )

        # ---- model_reliability: historical accuracy ---------------------
        acc = 0.5
        if backtest.metrics:
            mae1 = backtest.metrics.get("1", {}).get("mae")
            if mae1:
                acc = max(0.0, 1.0 - np.tanh(float(mae1) / current_price * 8))
        cal = 1.0 - self._calibration_error(backtest) if self._calibration_error(backtest) is not None else 0.5
        cov = 0.5
        c90 = backtest.coverage_90.get(1)
        if c90 is not None and c90 == c90:
            cov = max(0.0, 1.0 - abs(c90 - 0.90) * 4.0)
        if backtest.samples < 30:
            reasons.append(f"limited backtest history ({backtest.samples} samples)")
        model_reliability = 0.45 * acc + 0.25 * cal + 0.20 * cov + 0.10 * min(1.0, backtest.samples / 200)

        # ---- data_reliability: input trustworthiness --------------------
        data_quality = quality_score if quality_score is not None else 0.8
        match = match_confidence if match_confidence is not None else 0.5
        tier_ok = 1.0 if data_tier in (None, "TRUSTED") else (0.6 if data_tier == "REVIEW" else 0.2)
        if data_tier == "QUARANTINED":
            reasons.append("input data tier is QUARANTINED")
        data_reliability = (
            0.4 * quantity + 0.2 * freshness + 0.2 * data_quality + 0.1 * match + 0.1 * tier_ok
        )

        # ---- decision_confidence = g(forecast, model, data) -------------
        score = (
            CONFIDENCE_WEIGHTS["forecast"] * forecast_confidence
            + CONFIDENCE_WEIGHTS["model"] * model_reliability
            + CONFIDENCE_WEIGHTS["data"] * data_reliability
        )
        score = round(float(score), 3)
        if score >= 0.85:
            level = "HIGH"
        elif score >= 0.65:
            level = "MEDIUM"
        elif score >= 0.40:
            level = "LOW"
        else:
            level = "INSUFFICIENT"
        if level in ("LOW", "INSUFFICIENT"):
            reasons.append("overall evidence insufficient for a strong claim")

        return {
            "score": score,
            "level": level,
            "reasons": reasons,
            "forecast_confidence": round(float(forecast_confidence), 3),
            "model_reliability": round(float(model_reliability), 3),
            "data_reliability": round(float(data_reliability), 3),
            "components": {
                "quantity": round(float(quantity), 3),
                "freshness": round(float(freshness), 3),
                "agreement": round(float(agreement), 3),
                "stability": round(float(stability), 3),
                "volatility": round(float(volatility), 3),
                "historical_mae_acc": round(float(acc), 3),
                "calibration": round(float(cal), 3),
                "coverage": round(float(cov), 3),
                "data_quality": round(float(data_quality), 3),
                "match_confidence": round(float(match), 3),
            },
            "weights": CONFIDENCE_WEIGHTS,
        }

    # ------------------------------------------------------------------ #
    # Target probability
    # ------------------------------------------------------------------ #
    def target_probabilities_from_series(
        self,
        series: pd.Series,
        target: float,
        horizons_hours: list[int],
        category: str | None = None,
        regime: str | None = None,
        retailer: str | None = None,
        match_confidence: float | None = None,
        quality_score: float | None = None,
        data_tier: str | None = None,
    ) -> tuple[dict[str, float], ForecastResult | None, list[str]]:
        warnings: list[str] = []
        result: ForecastResult | None = None
        probs: dict[str, float] = {}
        if series.empty:
            return probs, None, ["no price history"]

        y = series.dropna().to_numpy(dtype=float)
        models = self._cached_models(y, max(horizons_hours))
        for h in sorted(horizons_hours):
            try:
                fc = self.forecast_from_series(
                    series, h, interval_level=0.9, category=category, models=models,
                    regime=regime, retailer=retailer, match_confidence=match_confidence,
                    quality_score=quality_score, data_tier=data_tier,
                )
                raw = _prob_below_target(fc.quantiles[h - 1], target)
                raw = float(np.clip(raw, 0.02, 0.98))
                calibrated = self.calibration.apply(
                    np.asarray([raw]), category, h, regime=regime, retailer=retailer
                )
                probs[self._horizon_label(h)] = round(float(calibrated[0]), 4)
                if result is None:
                    result = fc
                warnings.extend(fc.warnings)
            except ValueError as exc:
                warnings.append(f"horizon {h}h skipped: {exc}")
        if result is not None:
            result.calibration_key_used = self.calibration.last_used_key
        return probs, result, warnings

    @staticmethod
    def _horizon_label(hours: int) -> str:
        if hours % 24 == 0:
            days = hours // 24
            return f"{days}d" if days >= 1 else f"{hours}h"
        return f"{hours}h"

    # ------------------------------------------------------------------ #
    # Decision (blueprint section 25/26)
    # ------------------------------------------------------------------ #
    def decide(
        self,
        current_price: float,
        probs: dict[str, float],
        forecast: ForecastResult | None,
        target: float,
        max_wait_days: int | None = None,
        urgency: str = "normal",
    ) -> dict:
        """Decision with V1.2 machine-readable reason codes.

        The LLM never rewrites these numbers: it converts them to natural
        language, and every number in an answer must trace to this dict.
        """
        if forecast is None:
            return {
                "recommendation": "INSUFFICIENT_CONFIDENCE",
                "current_price": round(float(current_price), 2),
                "expected_price": None,
                "target_probability": None,
                "forecast_reliability": None,
                "data_reliability": None,
                "horizon_days": None,
                "reason_codes": ["NO_FORECAST_AVAILABLE"],
                "reasoning": ["no forecast available"],
            }

        level = forecast.confidence.get("level", "INSUFFICIENT")
        if level == "INSUFFICIENT":
            return {
                "recommendation": "INSUFFICIENT_CONFIDENCE",
                "current_price": round(float(current_price), 2),
                "expected_price": None,
                "target_probability": None,
                "forecast_reliability": round(float(forecast.confidence.get("model_reliability", 0.0)), 3),
                "data_reliability": round(float(forecast.confidence.get("data_reliability", 0.0)), 3),
                "horizon_days": forecast.horizon // 24,
                "reason_codes": ["INSUFFICIENT_EVIDENCE"],
                "reasoning": forecast.confidence.get("reasons", []),
            }

        horizon_days = forecast.horizon // 24
        key = f"{horizon_days}d"
        if key not in probs:
            key = min(probs, key=lambda k: abs(_days_from_label(k) - horizon_days)) if probs else None
        p_drop = probs.get(key, 0.0) if key else 0.0

        saving = max(0.0, current_price - target)
        expected_benefit = p_drop * saving

        wait_cost = current_price * (0.02 if urgency == "high" else 0.01)
        eu_wait = expected_benefit - wait_cost

        reasoning = [
            f"probability of reaching {target:.0f} INR within {horizon_days}d: {p_drop:.0%}",
            f"expected benefit of waiting: {expected_benefit:.0f} INR (wait cost {wait_cost:.0f} INR)",
        ]

        base = {
            "current_price": round(float(current_price), 2),
            "expected_price": round(float(forecast.quantiles[0, QUANTILES.index(0.5)]), 2),
            "target": round(float(target), 2),
            "target_probability": round(float(p_drop), 4),
            "forecast_reliability": round(float(forecast.confidence.get("model_reliability", 0.0)), 3),
            "data_reliability": round(float(forecast.confidence.get("data_reliability", 0.0)), 3),
            "horizon_days": horizon_days,
            "expected_saving": round(expected_benefit, 2),
            "probability_of_benefit": round(p_drop, 4),
            "reason_codes": [],
            "reasoning": reasoning,
        }

        if level == "LOW":
            reasoning.append("confidence is LOW - treat recommendation as advisory only")
            base["reason_codes"].append("LOW_CONFIDENCE_ADVISORY")
        if max_wait_days is not None and horizon_days > max_wait_days:
            return {
                **base,
                "recommendation": "BUY_NOW",
                "reason_codes": ["USER_DEADLINE_SHORTER_THAN_HORIZON"] + base["reason_codes"],
                "reasoning": reasoning + [f"user can wait only {max_wait_days} days; forecast horizon exceeds it"],
            }
        if eu_wait > 0 and p_drop >= 0.4:
            return {
                **base,
                "recommendation": "WAIT",
                "reason_codes": ["WAIT_EXPECTED_VALUE_POSITIVE", "TARGET_ATTAINABLE_WITHIN_HORIZON"]
                + base["reason_codes"],
                "reasoning": reasoning,
            }
        return {
            **base,
            "recommendation": "BUY_NOW",
            "reason_codes": ["WAIT_EXPECTED_VALUE_NEGATIVE"] + base["reason_codes"],
            "reasoning": reasoning + ["expected value of waiting does not justify the delay"],
        }


def _days_from_label(label: str) -> int:
    try:
        return int(label.rstrip("d"))
    except ValueError:
        return 999
