"""Regime detection + change-point detection (blueprint sections 12/13).

v1 uses cheap, explainable heuristics:
  - CUSUM-based change-point scan on recent prices
  - volatility/trend classification -> REGIME label
Later sprints can swap in HMM/Bayesian/ruptures models behind the same API.
"""

import numpy as np

REGIMES = [
    "NORMAL",
    "PROMOTION",
    "FLASH_SALE",
    "HIGH_DEMAND",
    "LOW_INVENTORY",
    "NEW_MODEL_RELEASE",
    "SEASONAL",
    "PRICE_WAR",
]


def detect_change_point(y: np.ndarray, threshold: float = 4.0) -> int | None:
    """One-sided CUSUM: returns index of the most recent structural break."""
    if len(y) < 15:
        return None
    mean = float(np.mean(y))
    std = float(np.std(y)) or 1.0
    cusum = np.cumsum((y - mean) / std)
    best = None
    best_val = 0.0
    for i in range(1, len(y) - 1):
        if abs(cusum[i]) > threshold and abs(cusum[i]) > best_val:
            best, best_val = i, abs(cusum[i])
    if best is None or len(y) - best < 3:
        return None
    return int(best)


def classify_regime(y: np.ndarray, change_point: int | None = None) -> dict:
    """Heuristic regime classification. Returns {'regime': str, 'signals': [...], 'stable': bool}."""
    if len(y) < 12:
        return {"regime": "INSUFFICIENT_DATA", "signals": ["too little history"], "stable": False}

    recent = y[-12:]
    base = y[-36:] if len(y) >= 36 else y
    ret = float(recent[-1] / base.mean() - 1)
    vol = float(recent.std(ddof=1) / base.mean())

    signals: list[str] = []
    regime = "NORMAL"
    if ret <= -0.05:
        regime = "PROMOTION" if vol < 0.06 else "PRICE_WAR"
        signals.append(f"price down {abs(ret):.1%} vs 36d mean")
    elif ret <= -0.02:
        regime = "PROMOTION"
        signals.append("mild discounting")
    elif ret >= 0.03:
        regime = "HIGH_DEMAND"
        signals.append(f"price up {ret:.1%}")
    if vol > 0.08:
        signals.append(f"high volatility {vol:.1%}")

    recent_break = change_point is not None and change_point >= len(y) - 10
    stable = not recent_break and vol < 0.05
    if recent_break:
        regime = "PRICE_WAR" if ret <= -0.05 else "REGIME_SHIFT"
        signals.append("recent change-point detected")

    return {"regime": regime, "signals": signals, "stable": stable}
