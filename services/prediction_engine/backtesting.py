"""Walk-forward backtesting (continuous evaluation backbone).

Splits history into expanding train windows; each fold builds the ensemble
(weights from the registry or equal) and forecasts `horizon` steps, scoring
against actuals. Produces:
  - per-horizon metrics (MAE/RMSE/quantile loss)
  - residual arrays |actual - p50| for conformal calibration
  - (claimed quantile, actual <= quantile) pairs for probability calibration
  - measured 90% conformal coverage per horizon
"""

from dataclasses import dataclass, field

import numpy as np

from prediction_engine.evaluation import summarize
from prediction_engine.models.base import QUANTILES, ForecastModel


@dataclass
class BacktestResult:
    metrics: dict = field(default_factory=dict)
    residuals: dict[int, np.ndarray] = field(default_factory=dict)  # horizon -> |actual - p50|
    residual_buckets: dict[int, dict[str, np.ndarray]] = field(default_factory=dict)  # horizon -> regime -> resid
    prob_outcome: list[tuple[float, int]] = field(default_factory=list)
    coverage_90: dict[int, float] = field(default_factory=dict)
    folds: int = 0
    samples: int = 0
    regimes_seen: list[str] = field(default_factory=list)


def walk_forward_backtest(
    y: np.ndarray,
    horizon: int,
    models: list[ForecastModel],
    weights: dict[str, float] | None = None,
    n_folds: int | None = None,
    min_train: int = 30,
    quantiles: list[float] | None = None,
    max_fold_horizon: int = 5,
    heavy: bool = False,
) -> BacktestResult:
    """Score the ensemble against actuals via expanding-window folds.

    By default only cheap models (naive/MA/ES/seasonal) are refit per fold;
    ARIMA/GBM are excluded from the fold loop unless `heavy=True`.
    """
    from prediction_engine.ensemble import Ensemble

    if not heavy:
        cheap = [m for m in models if getattr(m, "is_cheap", True)]
        if cheap:
            models = cheap

    quantiles = quantiles or QUANTILES
    y = np.asarray(y, dtype=float)
    n = len(y)
    fold_horizon = min(horizon, max_fold_horizon)
    if n < min_train + fold_horizon + 2:
        return BacktestResult()

    n_folds = n_folds or max(3, min(12, (n - min_train) // (fold_horizon * 2)))
    starts = np.linspace(min_train, n - fold_horizon - 1, n_folds, dtype=int)

    actuals: dict[int, list] = {h: [] for h in range(1, fold_horizon + 1)}
    paths: dict[int, list] = {h: [] for h in range(1, fold_horizon + 1)}
    prob_outcome: list[tuple[float, int]] = []
    step_regimes: dict[int, list[str | None]] = {h: [] for h in range(1, fold_horizon + 1)}

    for s in starts:
        train = y[:s]
        ensemble = Ensemble(models, weights)
        path, _ = ensemble.forecast(train, fold_horizon, quantiles)
        regime_label = classify_regime_at_fit(train)
        for h in range(1, fold_horizon + 1):
            actual = float(y[s + h])
            actuals[h].append(actual)
            paths[h].append(path[h - 1])
            step_regimes[h].append(regime_label)
            for i, q in enumerate(quantiles):
                prob_outcome.append((q, int(actual <= path[h - 1, i])))

    a_arrays = {h: np.asarray(v) for h, v in actuals.items() if v}
    p_arrays = {h: np.stack(v) for h, v in paths.items() if v}

    result = BacktestResult(folds=len(starts), samples=sum(len(v) for v in a_arrays.values()))
    result.metrics = summarize(a_arrays, p_arrays, quantiles)
    result.residuals = {h: np.abs(a_arrays[h] - p_arrays[h][:, quantiles.index(0.5)]) for h in a_arrays}
    result.residual_buckets = {
        h: _bucket_residuals(a_arrays[h], p_arrays[h][:, quantiles.index(0.5)], step_regimes[h])
        for h in a_arrays
    }
    result.prob_outcome = prob_outcome
    result.coverage_90 = _conformal_coverage(p_arrays, a_arrays, quantiles, 0.90)
    result.regimes_seen = sorted({r for rs in step_regimes.values() for r in rs if r})
    return result


def classify_regime_at_fit(train: np.ndarray) -> str | None:
    """Regime label attached to a backtest fold (heuristic, cheap)."""
    from prediction_engine.regime import classify_regime, detect_change_point

    if len(train) < 12:
        return None
    return classify_regime(train, detect_change_point(train)).get("regime")


def _bucket_residuals(
    actuals: np.ndarray, preds: np.ndarray, regimes: list[str | None]
) -> dict[str, np.ndarray]:
    """Exact per-step residual bucketing by fold regime (aligned by index)."""
    residuals = np.abs(actuals - preds)
    out: dict[str, list] = {}
    for resid, regime in zip(residuals, regimes):
        if regime:
            out.setdefault(regime, []).append(float(resid))
    return {k: np.asarray(v) for k, v in out.items()}


def _conformal_coverage(
    p_arrays: dict[int, np.ndarray],
    a_arrays: dict[int, np.ndarray],
    quantiles: list[float],
    level: float,
) -> dict[int, float]:
    """Measured coverage when applying conformal qhat from the same residuals."""
    from prediction_engine.conformal import conformal_quantile, coverage_rate

    q50 = quantiles.index(0.5)
    out: dict[int, float] = {}
    for h in p_arrays:
        residuals = np.abs(a_arrays[h] - p_arrays[h][:, q50])
        qhat = conformal_quantile(residuals, level)
        if qhat <= 0:
            out[h] = float("nan")
            continue
        preds = p_arrays[h][:, q50]
        out[h] = round(coverage_rate(preds - qhat, preds + qhat, a_arrays[h]), 4)
    return out
