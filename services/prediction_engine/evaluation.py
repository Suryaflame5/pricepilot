"""Evaluation metrics (blueprint section 20): MAE, RMSE, quantile loss,
Brier score, coverage, ECE."""

import numpy as np


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted))) if len(actual) else float("nan")


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2))) if len(actual) else float("nan")


def quantile_loss(actual: np.ndarray, predicted: np.ndarray, q: float) -> float:
    diff = actual - predicted
    return float(np.mean(np.maximum(q * diff, (q - 1) * diff))) if len(actual) else float("nan")


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean((probs - outcomes) ** 2)) if len(probs) else float("nan")


def directional_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Fraction of steps where the forecast move agrees in sign with the actual move."""
    if len(actual) < 2:
        return float("nan")
    a = np.diff(actual)
    p = np.diff(predicted)
    mask = a != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.sign(a[mask]) == np.sign(p[mask])))


def stability(actual: np.ndarray, predicted: np.ndarray, window: int = 5) -> float:
    """1 - coefficient-of-variation of rolling MAE (higher = more stable)."""
    if len(actual) < window + 1:
        return float("nan")
    errs = np.abs(np.asarray(actual) - np.asarray(predicted))
    rolling = np.convolve(errs, np.ones(window), "valid") / window
    mean, std = float(rolling.mean()), float(rolling.std(ddof=1))
    if mean <= 0:
        return float("nan")
    return max(0.0, min(1.0, 1.0 - std / mean))


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Symmetric Mean Absolute Percentage Error (percentage, 0-100%)."""
    if not len(actual):
        return float("nan")
    denom = (np.abs(actual) + np.abs(predicted)) / 2.0
    mask = denom > 1e-6
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denom[mask]) * 100.0)


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Percentage Error (percentage, 0-100%)."""
    if not len(actual):
        return float("nan")
    mask = np.abs(actual) > 1e-6
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100.0)


def winkler_score(
    actual: np.ndarray, lower: np.ndarray, upper: np.ndarray, alpha: float = 0.10
) -> float:
    """Winkler Interval Score for (1 - alpha) prediction intervals.
    Penalizes both interval width and observations outside bounds. Lower is better.
    """
    if not len(actual):
        return float("nan")
    width = upper - lower
    under_penalty = (2.0 / alpha) * (lower - actual) * (actual < lower)
    over_penalty = (2.0 / alpha) * (actual - upper) * (actual > upper)
    return float(np.mean(width + under_penalty + over_penalty))


def empirical_coverage(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Empirical coverage rate (fraction of actuals inside [lower, upper])."""
    if not len(actual):
        return float("nan")
    covered = (actual >= lower) & (actual <= upper)
    return float(np.mean(covered))


def summarize(actuals: dict[int, np.ndarray], paths: dict[int, np.ndarray], quantiles: list[float]) -> dict:
    """Per-horizon metrics from backtest records.

    actuals: {horizon: array of actuals}
    paths:   {horizon: (n_forecasts, n_quantiles) quantile paths}
    """
    q_index = {q: i for i, q in enumerate(quantiles)}
    out: dict = {}
    for h, acts in actuals.items():
        ph = paths.get(h)
        if ph is None or len(acts) == 0:
            continue
        preds = ph[:, q_index[0.5]]

        metrics_h = {
            "mae": round(mae(acts, preds), 2),
            "rmse": round(rmse(acts, preds), 2),
            "smape": round(smape(acts, preds), 2),
            "mape": round(mape(acts, preds), 2),
            "n": int(len(acts)),
            "quantile_loss_50": round(quantile_loss(acts, preds, 0.5), 2),
            "directional_accuracy": round(directional_accuracy(acts, preds), 4),
            "stability": round(stability(acts, preds), 4),
        }

        # Conformal interval metrics if P10 & P90 or P05 & P95 exist
        if 0.10 in q_index and 0.90 in q_index:
            lo90 = ph[:, q_index[0.10]]
            hi90 = ph[:, q_index[0.90]]
            metrics_h["winkler_score_90"] = round(winkler_score(acts, lo90, hi90, alpha=0.10), 2)
            metrics_h["coverage_90"] = round(empirical_coverage(acts, lo90, hi90), 4)

        out[str(h)] = metrics_h
    return out
