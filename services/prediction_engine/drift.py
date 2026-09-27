"""Prediction monitoring: feature drift + live coverage.

Feature drift: KS test / PSI on recent price-return distribution vs baseline.
Coverage monitoring: from stored predictions + subsequent actuals
(prediction_outcomes), rolling 90% interval coverage + sharpness. Anything
outside tolerance raises a calibration.drift event for recalibration.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np

DRIFT_PVALUE_THRESHOLD = 0.05
COVERAGE_ABS_TOLERANCE = 0.05


@dataclass
class DriftReport:
    drifted: bool
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"drifted": self.drifted, "reasons": self.reasons, "details": self.details}


def _ecdf(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    sorted_x = np.sort(x)
    return sorted_x, np.arange(1, len(sorted_x) + 1) / len(sorted_x)


def ks_test(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov (D statistic, approximate p-value)."""
    if len(a) < 5 or len(b) < 5:
        return 0.0, 1.0
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n, m = len(a), len(b)
    a_sorted, b_sorted = np.sort(a), np.sort(b)
    x = np.sort(np.concatenate([a_sorted, b_sorted]))
    cdf_a = np.searchsorted(a_sorted, x, side="right") / n
    cdf_b = np.searchsorted(b_sorted, x, side="right") / m
    d = float(np.max(np.abs(cdf_a - cdf_b)))
    lam = d * np.sqrt((n * m) / (n + m))
    p = 2.0 * np.exp(-2.0 * lam * lam) if lam < 3 else 0.0
    return d, p


def psi(reference: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
    """Population Stability Index between two distributions."""
    if len(reference) == 0 or len(current) == 0:
        return float("nan")
    edges = np.linspace(min(reference.min(), current.min()), max(reference.max(), current.max()), n_bins + 1)
    if len(np.unique(edges)) < 3:
        return float("nan")
    ref_h = np.histogram(reference, bins=edges)[0].astype(float) / len(reference)
    cur_h = np.histogram(current, bins=edges)[0].astype(float) / len(current)
    ref_h = np.clip(ref_h, 1e-6, None)
    cur_h = np.clip(cur_h, 1e-6, None)
    return float(np.sum((cur_h - ref_h) * np.log(cur_h / ref_h)))


def detect_feature_drift(
    baseline: np.ndarray,
    recent: np.ndarray,
    *,
    p_threshold: float = DRIFT_PVALUE_THRESHOLD,
    psi_threshold: float = 0.25,
) -> DriftReport:
    """Compare return distributions. Recent: most recent observations.

    The ALARM decision is driven by the two-sample KS test on returns; PSI is
    recorded as a supporting diagnostic (it is too noisy on low-variance
    return series to be a reliable alarm by itself).
    """
    report = DriftReport(drifted=False)
    if len(baseline) < 10 or len(recent) < 5:
        report.reasons.append("insufficient data for drift test")
        return report

    def returns(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        return np.diff(x) / np.where(np.abs(x[:-1]) > 1e-9, np.abs(x[:-1]), 1.0)

    b_ret, r_ret = returns(baseline), returns(recent)
    d, p = ks_test(b_ret, r_ret)
    ps = psi(b_ret, r_ret)
    report.details = {"ks_d": round(d, 4), "ks_p": round(p, 4), "psi": round(ps, 4) if ps == ps else None}

    if p < p_threshold:
        report.reasons.append(f"return distribution shifted (KS p={p:.4f})")
        report.drifted = True
    return report


def evaluate_coverage(
    in_interval: list[bool],
    level: float = 0.90,
    tolerance: float = COVERAGE_ABS_TOLERANCE,
) -> dict[str, Any]:
    """Rolling coverage check over prediction outcomes."""
    if not in_interval:
        return {"coverage": None, "n": 0, "within_tolerance": None, "drifted": False}
    coverage = float(np.mean(np.asarray(in_interval, dtype=float)))
    drifted = abs(coverage - level) > tolerance
    return {
        "coverage": round(coverage, 4),
        "n": len(in_interval),
        "target": level,
        "within_tolerance": not drifted,
        "drifted": drifted,
    }
