"""Layer 1 - statistical baselines: naive, moving average, exponential smoothing,
seasonal naive. These establish the bar deep learning must beat."""

import numpy as np

from prediction_engine.models.base import ForecastModel, _residual_quantiles


class NaiveForecaster(ForecastModel):
    name = "naive"

    def forecast_quantiles(self, y, horizon, quantiles=None):
        quantiles = quantiles or [0.5]
        if len(y) < 3:
            point = np.full(horizon, float(y[-1]) if len(y) else 0.0)
            return np.repeat(point[:, None], len(quantiles), axis=1)
        residuals = np.diff(y)
        point = np.full(horizon, float(y[-1]))
        return _residual_quantiles(point, residuals, quantiles)


class MovingAverageForecaster(ForecastModel):
    name = "moving_average"

    def __init__(self, window: int = 7) -> None:
        self.window = window

    def forecast_quantiles(self, y, horizon, quantiles=None):
        quantiles = quantiles or [0.5]
        if len(y) < self.window + 2:
            return NaiveForecaster().forecast_quantiles(y, horizon, quantiles)
        w = y[-self.window :]
        point = np.full(horizon, float(w.mean()))
        residuals = w - np.convolve(y[:-1], np.ones(self.window) / self.window, mode="valid")
        return _residual_quantiles(point, residuals[: max(len(residuals), 1)], quantiles)


class ExponentialSmoothingForecaster(ForecastModel):
    name = "exp_smoothing"

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = alpha

    def forecast_quantiles(self, y, horizon, quantiles=None):
        quantiles = quantiles or [0.5]
        if len(y) < 4:
            return NaiveForecaster().forecast_quantiles(y, horizon, quantiles)
        level = float(y[0])
        residuals = []
        for v in y[1:]:
            residuals.append(v - level)
            level = self.alpha * v + (1 - self.alpha) * level
        point = np.full(horizon, level)
        return _residual_quantiles(point, np.asarray(residuals), quantiles)


class SeasonalNaiveForecaster(ForecastModel):
    """Flat forecast shifted by one week - captures weekly retail cycles."""

    name = "seasonal_naive"

    def __init__(self, period: int = 7) -> None:
        self.period = period

    def forecast_quantiles(self, y, horizon, quantiles=None):
        quantiles = quantiles or [0.5]
        if len(y) < self.period + 3:
            return NaiveForecaster().forecast_quantiles(y, horizon, quantiles)
        point = np.full(horizon, float(y[-self.period]))
        residuals = np.diff(y[:: max(1, self.period // 2)])
        if len(residuals) == 0:
            residuals = np.diff(y)
        return _residual_quantiles(point, residuals, quantiles)


BASELINE_MODELS = [
    NaiveForecaster(),
    MovingAverageForecaster(window=7),
    ExponentialSmoothingForecaster(alpha=0.3),
    SeasonalNaiveForecaster(period=7),
]
