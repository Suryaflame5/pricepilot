"""Layer 5 - ensemble with learned weights (blueprint section 10/11).

Weights are optimized against held-out quantile loss (SLSQP over the simplex).
Weights are re-learned in backtests and stored in the model registry, so they
are never hardcoded forever. Disagreement between members becomes a signal.
"""

import numpy as np

from prediction_engine.models.base import QUANTILES, ForecastModel

DEFAULT_WEIGHTS = {
    "gbm": 0.25,
    "arima": 0.20,
    "exp_smoothing": 0.15,
    "moving_average": 0.15,
    "naive": 0.10,
    "seasonal_naive": 0.10,
    "baseline_naive": 0.05,
}


class Ensemble:
    def __init__(self, models: list[ForecastModel], weights: dict[str, float] | None = None) -> None:
        self.models = models
        self.weights = {m.name: weights.get(m.name, 0.0) for m in models} if weights else {
            m.name: 1.0 / len(models) for m in models
        }
        self._normalize()

    def _normalize(self) -> None:
        total = sum(self.weights.values()) or 1.0
        self.weights = {k: v / total for k, v in self.weights.items()}

    def forecast(
        self,
        y: np.ndarray,
        horizon: int,
        quantiles: list[float] | None = None,
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Return (weighted quantile path, per-model point forecasts)."""
        quantiles = quantiles or QUANTILES
        paths: dict[str, np.ndarray] = {}
        points: dict[str, float] = {}
        for m in self.models:
            try:
                path = m.forecast_quantiles(y, horizon, quantiles)
            except Exception:
                path = np.full((horizon, len(quantiles)), float(y[-1]))
            paths[m.name] = path
            points[m.name] = float(path[0, list(quantiles).index(0.5)])

        combined = np.zeros((horizon, len(quantiles)))
        for name, path in paths.items():
            combined += self.weights.get(name, 0.0) * path
        return combined, points

    def disagreement(self, points: dict[str, float]) -> float:
        """Normalized std of member point forecasts -> uncertainty signal."""
        vals = np.asarray(list(points.values()))
        return float(vals.std(ddof=1)) if len(vals) > 1 else 0.0

    def fit_weights(self, y: np.ndarray, horizon: int, quantiles: list[float]) -> None:
        """Learn simplex weights minimizing quantile loss on the last 25% of history.

        Uses the last fold of the series as validation: predict with each model
        from each start index, compare against actuals.
        """
        n = len(y)
        if n < 40:
            return
        starts = list(range(max(0, n - n // 4), n - horizon))
        if len(starts) < 2:
            return
        member_paths: list[np.ndarray] = []
        for m in self.models:
            try:
                paths = np.stack(
                    [m.forecast_quantiles(y[:s], horizon, quantiles)[0] for s in starts]
                )
                member_paths.append(paths)
            except Exception:
                member_paths.append(np.full((len(starts), len(quantiles)), float(y[starts[0]])))

        if len(member_paths) != len(self.models):
            return
        actuals = np.asarray([float(y[s + horizon]) if s + horizon < n else np.nan for s in starts])
        mask = ~np.isnan(actuals)
        if mask.sum() < 2:
            return
        member_paths = [p[mask] for p in member_paths]
        actuals = actuals[mask]

        n_m, nq = len(member_paths), len(quantiles)
        X = np.stack(member_paths)  # (n_models, n_folds, nq)

        def loss(w: np.ndarray) -> float:
            pred = np.tensordot(w, X, axes=(0, 0))  # (n_folds, nq)
            errs = []
            for i, q in enumerate(quantiles):
                diff = actuals - pred[:, i]
                errs.append(np.maximum(q * diff, (q - 1) * diff).mean())
            return float(np.mean(errs))

        from scipy.optimize import minimize

        w0 = np.asarray([self.weights[m.name] for m in self.models])
        res = minimize(
            loss,
            w0,
            method="SLSQP",
            bounds=[(0.0, 1.0)] * n_m,
            constraints={"type": "eq", "fun": lambda w: w.sum() - 1.0},
            options={"maxiter": 200, "ftol": 1e-6},
        )
        if res.success:
            self.weights = {m.name: float(max(0.0, res.x[i])) for i, m in enumerate(self.models)}
            self._normalize()
