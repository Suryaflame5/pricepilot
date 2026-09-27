"""Layer 2 - gradient boosting quantile regression (LightGBM preferred,
scikit-learn GradientBoosting fallback). Direct multi-horizon: one model
per (horizon, quantile) trained on lag + statistical features."""

import numpy as np

from prediction_engine.models.base import ForecastModel, QUANTILES

try:
    from lightgbm import LGBMRegressor as _LGBM

    _HAS_LGBM = True
except ImportError:
    _LGBM = None
    _HAS_LGBM = False

from sklearn.ensemble import GradientBoostingRegressor

TRAIN_QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
LAG_COUNT = 14
MIN_SAMPLES = 60


def _build_regressor(alpha: float):
    if _HAS_LGBM:
        return _LGBM(
            objective="quantile",
            alpha=alpha,
            n_estimators=80,
            learning_rate=0.06,
            max_depth=4,
            min_child_samples=15,
            verbose=-1,
        )
    return GradientBoostingRegressor(
        loss="quantile",
        alpha=alpha,
        n_estimators=80,
        learning_rate=0.06,
        max_depth=4,
        random_state=42,
    )


def _lag_features(y: np.ndarray) -> np.ndarray:
    """Row t: lag prices + relative normalized returns + rolling stats (mean, volatility, momentum)."""
    if len(y) <= LAG_COUNT:
        y = np.concatenate([np.full(LAG_COUNT - len(y) + 1, float(y[0])), y])
    out = []
    for t in range(len(y) - LAG_COUNT):
        win = y[t : t + LAG_COUNT]
        curr = win[-1]
        eps = 1e-6

        # 1. Raw lag prices (14 features)
        raw_lags = win

        # 2. Relative percentage returns vs current price (14 features)
        rel_returns = (win - curr) / (curr + eps)

        # 3. Rolling mean ratios
        m3_ratio = (np.mean(win[-3:]) - curr) / (curr + eps)
        m7_ratio = (np.mean(win[-7:]) - curr) / (curr + eps)
        m14_ratio = (np.mean(win) - curr) / (curr + eps)

        # 4. Rolling volatility (standard deviation of relative returns)
        vol7 = float(np.std(win[-7:]) / (curr + eps))
        vol14 = float(np.std(win) / (curr + eps))

        # 5. Min/max spread ratio
        spread = float((np.max(win) - np.min(win)) / (curr + eps))

        # 6. Momentum (slope across 7-day and 14-day intervals)
        mom7 = float((curr - win[-7]) / (win[-7] + eps))
        mom14 = float((curr - win[0]) / (win[0] + eps))

        stats = np.array([m3_ratio, m7_ratio, m14_ratio, vol7, vol14, spread, mom7, mom14])
        feat = np.concatenate([raw_lags, rel_returns, stats])
        out.append(feat)
    return np.asarray(out)


class GBMPointForecaster(ForecastModel):
    """Direct multi-horizon GBM. Trained per call on the given history."""

    name = "gbm"

    def __init__(self, max_horizon: int = 90) -> None:
        self.max_horizon = max_horizon
        self._models: dict[tuple[int, float], object] = {}

    def fit(self, y: np.ndarray, horizons: list[int]) -> None:
        y = np.asarray(y, dtype=float)
        X = _lag_features(y)
        self._models.clear()
        for h in horizons:
            if h > self.max_horizon or len(y) - LAG_COUNT - h <= 0:
                continue
            y_target = y[LAG_COUNT + h : len(y)] if h > 0 else y[LAG_COUNT:]
            X_train, y_train = X[: len(y_target)], y_target
            if len(y_train) < MIN_SAMPLES:
                continue
            for a in TRAIN_QUANTILES:
                self._models[(h, a)] = _build_regressor(a).fit(X_train, y_train)

    def forecast_quantiles(self, y, horizon, quantiles=None):
        quantiles = quantiles or QUANTILES
        if len(y) < MIN_SAMPLES or not self._models:
            from prediction_engine.models.baseline import NaiveForecaster

            return NaiveForecaster().forecast_quantiles(y, horizon, quantiles)

        X = _lag_features(y)
        last = X[-1:]
        out = np.full((horizon, len(quantiles)), float(y[-1]))
        available = sorted({h for h, _ in self._models})
        for i, h in enumerate(range(1, horizon + 1)):
            h_eff = min(available, key=lambda a: abs(a - h))  # nearest trained horizon
            if (h_eff, 0.5) not in self._models:
                continue
            preds = {a: self._models[(h_eff, a)].predict(last)[0] for a in TRAIN_QUANTILES}
            out[i] = np.sort(_interp_quantiles(preds, quantiles))
        return out


def fit_horizons(max_horizon: int) -> list[int]:
    """Sparse horizon grid - GBM trains per (horizon, quantile), so we keep
    the grid small and map every requested horizon to the nearest trained one."""
    grid = [1, 2, 3, 5, 7, 14, 21, 30]
    if max_horizon > 30:
        grid += [45, 60, 90]
    return [h for h in grid if h <= max_horizon] or [1]


def _interp_quantiles(preds: dict[float, float], quantiles: list[float]) -> np.ndarray:
    """Map 5 trained quantiles to the 7 requested via interpolation + flat extrapolation."""
    qs = np.asarray(sorted(preds))
    vals = np.asarray([preds[q] for q in qs])
    return np.interp(quantiles, qs, vals)


def fit_gbm_models(y: np.ndarray, horizons: list[int]) -> GBMPointForecaster:
    model = GBMPointForecaster(max_horizon=max(horizons))
    model.fit(y, horizons)
    return model
