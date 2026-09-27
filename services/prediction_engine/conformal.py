"""Conformal prediction (blueprint section 16), V1.1: regime-conditional.

Split conformal on backtest residuals, bucketed by regime: under
PROMOTION / HIGH_VOLATILITY the residual distribution is wider, so intervals
are correctly wider there - that is a feature, not a defect. Each regime
bucket has its own qhat; insufficient residuals in a bucket fall back to the
global (all-regime) qhat, then to a volatility heuristic.

Buckets are persisted to {conformal_dir}/residuals_{key}.json as fitted qhats
per horizon, refreshed by the continuous backtest.
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MIN_RESIDUALS_FOR_BUCKET = 20
FALLBACK_BUCKET = "GLOBAL"


def conformal_quantile(residuals: np.ndarray, level: float) -> float:
    """Split conformal quantile: qhat = quantile of residuals at (1 - alpha)(1 + 1/n)."""
    if len(residuals) == 0:
        return 0.0
    n = len(residuals)
    alpha = 1.0 - level
    q_level = min(1.0, (np.ceil((n + 1) * (1 - alpha)) / n))
    return float(np.quantile(np.abs(residuals), q_level))


def interval(point: float, qhat: float) -> tuple[float, float]:
    return (round(max(0.0, point - qhat), 2), round(point + qhat, 2))


def coverage_rate(lower: np.ndarray, upper: np.ndarray, actual: np.ndarray) -> float:
    if len(actual) == 0:
        return float("nan")
    return float(np.mean((actual >= lower) & (actual <= upper)))


def coverage_gap(coverage: float, level: float) -> float:
    if np.isnan(coverage):
        return float("nan")
    return float(coverage - level)


class RegimeConformalStore:
    """Per-regime qhats per horizon, persisted to disk.

    qhats = {horizon: {regime: qhat, "GLOBAL": qhat}} plus n per bucket.
    """

    def __init__(self, conformal_dir: str | Path | None = None) -> None:
        self.conformal_dir = Path(conformal_dir) if conformal_dir else None
        self._data: dict[int, dict[str, Any]] = {}

    def _path(self) -> Path | None:
        if not self.conformal_dir:
            return None
        return self.conformal_dir / "regime_residuals.json"

    def load(self) -> None:
        path = self._path()
        if path is None or not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._data = {int(k): v for k, v in data.get("buckets", {}).items()}
        except (OSError, json.JSONDecodeError):
            logger.warning("conformal store load failed")

    def save(self) -> None:
        path = self._path()
        if path is None:
            return
        self.conformal_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"buckets": {str(k): v for k, v in self._data.items()}},
                indent=2,
            )
        )

    def fit_bucket(self, horizon: int, regime: str, residuals: np.ndarray, level: float) -> bool:
        residuals = np.asarray(residuals, dtype=float)
        bucket = self._data.setdefault(
            int(horizon), {"GLOBAL": {"qhat": 0.0, "n": 0}, "buckets": {}}
        )
        if len(residuals) >= MIN_RESIDUALS_FOR_BUCKET:
            bucket["buckets"][str(regime)] = {
                "qhat": conformal_quantile(residuals, level),
                "n": int(len(residuals)),
            }
        if len(residuals) >= 1:
            bucket["GLOBAL"] = {
                "qhat": conformal_quantile(residuals, level),
                "n": int(len(residuals)),
            }
        return True

    def qhat_for(self, horizon: int, regime: str, level: float, fallback_qhat: float | None = None) -> tuple[float, str]:
        """Return (qhat, bucket_used). Prefers the regime bucket, then GLOBAL,
        then the caller's heuristic fallback."""
        bucket = self._data.get(int(horizon))
        if bucket:
            reg = bucket.get("buckets", {}).get(str(regime))
            if reg and reg["qhat"] > 0:
                return reg["qhat"], str(regime)
            g = bucket.get("GLOBAL")
            if g and g["qhat"] > 0:
                return g["qhat"], FALLBACK_BUCKET
        return fallback_qhat or 0.0, "heuristic"

    def state(self) -> dict[str, Any]:
        return {"buckets": self._data, "min_residuals_per_bucket": MIN_RESIDUALS_FOR_BUCKET}
