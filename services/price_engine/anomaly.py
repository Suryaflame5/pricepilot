"""Anomaly detection for incoming observations.

A price is only trusted after screening. Signals, combined conservatively:
1. Robust z-score (MAD) against the listing's recent history.
2. Sudden-change detection vs the previous point (relative + diff z).
3. Retailer-specific sanity thresholds (a 40% drop may be a promo for one
   retailer and garbage for another).
4. Isolation forest over engineered features (when enough history exists).

Verdict: anomaly_score in [0, 1] (higher = more anomalous), is_anomaly with
reasons. The pipeline quarantines/verifies before anything reaches forecasters.
"""

import statistics
from dataclasses import dataclass, field
from typing import Any

try:
    from sklearn.ensemble import IsolationForest
except ImportError:  # pragma: no cover - optional dependency
    IsolationForest = None

# Retailer-specific jump thresholds: pct change beyond these is flagged outright
RETAILER_THRESHOLDS: dict[str, dict[str, float]] = {
    "amazon": {"max_drop_pct": 0.35, "max_spike_pct": 0.60},
    "flipkart": {"max_drop_pct": 0.40, "max_spike_pct": 0.60},
    "croma": {"max_drop_pct": 0.30, "max_spike_pct": 0.50},
    "reliance_digital": {"max_drop_pct": 0.30, "max_spike_pct": 0.50},
    "mock": {"max_drop_pct": 0.50, "max_spike_pct": 0.80},
}
DEFAULT_THRESHOLDS = {"max_drop_pct": 0.50, "max_spike_pct": 0.75}

# Sample count needed before a signal is statistically meaningful
MIN_HISTORY_FOR_ZSCORE = 6
MIN_HISTORY_FOR_IFOREST = 20

ISOLATION_RANDOM_STATE = 7


@dataclass
class AnomalyVerdict:
    is_anomaly: bool = False
    score: float = 0.0  # 0..1, higher = more anomalous
    reasons: dict[str, Any] = field(default_factory=dict)
    signals: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_anomaly": self.is_anomaly,
            "score": round(self.score, 6),
            "reasons": self.reasons,
            "signals": self.signals,
        }


def _robust_z(value: float, series: list[float]) -> float | None:
    """MAD-based z-score; None when series is too small or degenerate."""
    if len(series) < MIN_HISTORY_FOR_ZSCORE:
        return None
    median = statistics.median(series)
    mad = statistics.median([abs(x - median) for x in series])
    if mad <= 0:
        return None
    return abs(value - median) / (1.4826 * mad)


def _pct_change(value: float, previous: float | None) -> float | None:
    if previous in (None, 0):
        return None
    return (value - previous) / previous


def _diff_z(value: float, previous: float, diffs: list[float]) -> float | None:
    if len(diffs) < MIN_HISTORY_FOR_ZSCORE:
        return None
    med = statistics.median(diffs)
    mad = statistics.median([abs(d - med) for d in diffs])
    if mad <= 0:
        return None
    return abs((value - previous) - med) / (1.4826 * mad)


def _isolation_score(value: float, history: list[float]) -> float | None:
    """IsolationForest on [price, pct_change, zscore]-style features.

    Returns a normalized anomaly probability in [0,1] or None when unavailable.
    """
    if IsolationForest is None or len(history) < MIN_HISTORY_FOR_IFOREST:
        return None
    hist = list(history)
    series = hist + [value]
    pct = [0.0]
    for i in range(1, len(series)):
        prev = series[i - 1]
        pct.append((series[i] - prev) / prev if prev else 0.0)
    features = [[p, c] for p, c in zip(series, pct)]
    model = IsolationForest(
        n_estimators=100, contamination="auto", random_state=ISOLATION_RANDOM_STATE
    )
    model.fit(features)
    scores = model.decision_function(features)  # higher = more normal
    s_min, s_max = min(scores), max(scores)
    norm = (s_max - scores[-1]) / (s_max - s_min) if s_max > s_min else 0.0
    return min(1.0, max(0.0, norm))


def detect_anomaly(
    value: float,
    history: list[float],
    previous: float | None = None,
    retailer: str | None = None,
) -> AnomalyVerdict:
    """Screen a new price against its listing history. history = past effective prices (asc time)."""
    verdict = AnomalyVerdict()
    th = RETAILER_THRESHOLDS.get(retailer or "", DEFAULT_THRESHOLDS)

    z = _robust_z(value, history)
    if z is not None:
        verdict.signals["robust_z"] = z
        if z >= 3.0:
            verdict.reasons["robust_z"] = f"|z|={z:.2f} beyond 3.0"
            verdict.score = max(verdict.score, min(1.0, (z - 3.0) / 5.0))

    pct = _pct_change(value, previous)
    if pct is not None:
        verdict.signals["pct_change"] = pct
        if pct <= -th["max_drop_pct"]:
            verdict.reasons["retailer_threshold"] = (
                f"drop of {abs(pct):.1%} exceeds retailer max {th['max_drop_pct']:.0%}"
            )
            verdict.score = max(verdict.score, 0.9)
        elif pct >= th["max_spike_pct"]:
            verdict.reasons["retailer_threshold"] = (
                f"spike of {pct:.1%} exceeds retailer max {th['max_spike_pct']:.0%}"
            )
            verdict.score = max(verdict.score, 0.8)

    if previous is not None and len(history) >= 2:
        diffs = [history[i] - history[i - 1] for i in range(1, len(history))]
        dz = _diff_z(value, previous, diffs)
        if dz is not None:
            verdict.signals["diff_z"] = dz
            if dz >= 4.0:
                verdict.reasons["sudden_change"] = f"step of |{value - previous:,.0f}| is {dz:.1f} sigma"
                verdict.score = max(verdict.score, min(1.0, (dz - 4.0) / 6.0))

    iso = _isolation_score(value, history)
    if iso is not None:
        verdict.signals["isolation_forest"] = iso
        if iso >= 0.8:
            verdict.reasons["isolation_forest"] = f"iForest anomaly prob {iso:.2f}"
            verdict.score = max(verdict.score, iso)

    verdict.is_anomaly = verdict.score >= 0.5 or bool(verdict.reasons)
    return verdict
