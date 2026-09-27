"""Uncertainty engine - probability calibration (blueprint section 15, V1.1 upgrade).

Calibrates raw model probabilities (e.g. P(target reached) = 0.91) into
honest probabilities (0.84) using isotonic regression on backtest
(probability, outcome) pairs.

V1.1: hierarchical keys with disciplined backoff:
    (category, horizon, regime, retailer) -> (category, horizon, regime)
    -> (category, horizon) -> (horizon, global)
Fits only with a minimum number of (prob, outcome) pairs; otherwise the key
falls through to a coarser bucket. The last-used key is recorded so monitors
can see which calibration curve was actually applied.
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MIN_CALIBRATION_PAIRS = 50


def expected_calibration_error(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    """Binned ECE: |mean(outcome) - mean(prob)| weighted by bin size."""
    if len(probs) < 10:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    count = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (probs >= lo) & (probs < hi)
        if i == n_bins - 1:
            mask = mask | (probs == 1.0)
        n = int(mask.sum())
        if n == 0:
            continue
        total += n * abs(outcomes[mask].mean() - probs[mask].mean())
        count += n
    return float(total / count) if count else float("nan")


def reliability_diagram(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> list[dict[str, Any]]:
    """Binned (mean_prob, mean_outcome, count) points for plotting/reporting."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    points: list[dict[str, Any]] = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (probs >= lo) & (probs < hi)
        if i == n_bins - 1:
            mask = mask | (probs == 1.0)
        n = int(mask.sum())
        if n == 0:
            continue
        points.append(
            {
                "bin": (round(lo, 2), round(hi, 2)),
                "n": n,
                "mean_prob": round(float(probs[mask].mean()), 4),
                "mean_outcome": round(float(outcomes[mask].mean()), 4),
            }
        )
    return points


class ProbabilityCalibrator:
    """Isotonic calibration of event probabilities, min-samples guarded."""

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self.store_dir = Path(store_dir) if store_dir else None
        self._reg = None
        self.n_pairs = 0

    def fit(self, probs: np.ndarray, outcomes: np.ndarray, min_pairs: int = MIN_CALIBRATION_PAIRS) -> bool:
        """Fit only if enough pairs exist; returns whether a fit happened."""
        probs = np.asarray(probs, dtype=float)
        outcomes = np.asarray(outcomes, dtype=int)
        if len(probs) < min_pairs:
            self._reg = None
            self.n_pairs = len(probs)
            return False
        from sklearn.isotonic import IsotonicRegression

        self._reg = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(
            probs, outcomes
        )
        self.n_pairs = len(probs)
        return True

    def calibrate(self, probs: np.ndarray | float) -> np.ndarray:
        if self._reg is None:
            return np.asarray(probs, dtype=float)
        return np.asarray(self._reg.predict(probs), dtype=float)


def _calibration_key(category: str | None, horizon: int, regime: str | None = None, retailer: str | None = None) -> str:
    parts = [category or "default", str(int(horizon))]
    if regime:
        parts.append(str(regime))
    if retailer:
        parts.append(str(retailer))
    return ":".join(parts)


class CalibrationStore:
    """Hierarchical isotonic curves persisted as point representations.

    apply() walks specific -> category -> global; records the key that matched
    so monitoring can attribute calibration quality.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self.store_dir = Path(store_dir) if store_dir else None
        self.last_used_key: str | None = None
        self.last_used_n_pairs: int | None = None

    def _path(self, key: str) -> Path | None:
        if not self.store_dir:
            return None
        return self.store_dir / f"{key}.json"

    def _load(self, key: str) -> tuple[np.ndarray, np.ndarray] | None:
        path = self._path(key)
        if path is None or not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        pts = np.asarray(data.get("points", []))
        if len(pts) < 2:
            return None
        return pts[:, 0], pts[:, 1]

    def _hierarchy(self, category: str | None, horizon: int, regime: str | None = None, retailer: str | None = None) -> list[str]:
        keys = []
        if regime or retailer:
            keys.append(_calibration_key(category, horizon, regime, retailer))
            if regime:
                keys.append(_calibration_key(category, horizon, regime))
        keys.append(_calibration_key(category, horizon))
        keys.append(_calibration_key(None, horizon))
        return keys

    def apply(
        self,
        raw_probs: np.ndarray,
        category: str | None,
        horizon: int,
        regime: str | None = None,
        retailer: str | None = None,
    ) -> np.ndarray:
        self.last_used_key = None
        self.last_used_n_pairs = None
        for key in self._hierarchy(category, horizon, regime, retailer):
            loaded = self._load(key)
            if loaded is None:
                continue
            xs, ys = loaded
            self.last_used_key = key
            self.last_used_n_pairs = None
            return np.interp(raw_probs, xs, ys)
        return raw_probs

    def get_key(self, category: str | None, horizon: int, regime: str | None = None, retailer: str | None = None) -> str | None:
        """Return the key that WOULD match (for reports), or None if uncalibrated."""
        for key in self._hierarchy(category, horizon, regime, retailer):
            if self._load(key) is not None:
                return key
        return None

    def save_fit(self, probs: np.ndarray, outcomes: np.ndarray, key: str, min_pairs: int = MIN_CALIBRATION_PAIRS) -> bool:
        """Fit from data and persist under `key` (returns whether a fit occurred)."""
        if self.store_dir is None:
            return False
        calibrator = ProbabilityCalibrator()
        if not calibrator.fit(probs, outcomes, min_pairs=min_pairs):
            return False
        xs = np.linspace(0.0, 1.0, 201)
        ys = calibrator.calibrate(xs)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        (self.store_dir / f"{key}.json").write_text(
            json.dumps(
                {
                    "points": [[float(x), float(y)] for x, y in zip(xs, ys)],
                    "key": key,
                    "n_pairs": int(calibrator.n_pairs),
                    "ece": round(expected_calibration_error(probs, outcomes), 4)
                    if len(probs) >= 10
                    else None,
                    "min_pairs": min_pairs,
                }
            )
        )
        return True

    def summary(self) -> dict[str, Any]:
        """All stored calibration curves (key, n_pairs, ece) for monitoring."""
        if not self.store_dir or not self.store_dir.exists():
            return {"curves": []}
        out = []
        for path in sorted(self.store_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                out.append(
                    {
                        "key": data.get("key", path.stem),
                        "n_pairs": data.get("n_pairs"),
                        "ece": data.get("ece"),
                    }
                )
            except (OSError, json.JSONDecodeError):
                continue
        return {"curves": out}
