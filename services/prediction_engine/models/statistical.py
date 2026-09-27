"""Layer 1b - ARIMA / SARIMA via statsmodels (lazy import; falls back to naive)."""

import numpy as np

from prediction_engine.models.base import ForecastModel, QUANTILES, z_normal


class ARIMAForecaster(ForecastModel):
    name = "arima"
    is_cheap = False  # refitting per backtest fold is expensive

    def __init__(
        self,
        order: tuple[int, int, int] | None = None,
        auto_order: bool = False,
    ) -> None:
        self.order = order
        self.auto_order = auto_order

    def forecast_quantiles(self, y, horizon, quantiles=None):
        quantiles = quantiles or QUANTILES
        if len(y) < 8:
            return _fallback(y, horizon, quantiles)
        try:
            from statsmodels.tsa.arima.model import ARIMA

            order = self.order
            if order is None and self.auto_order and len(y) <= 300:
                order = _pick_order(y)
            order = order or (1, 1, 0)
            model = ARIMA(y, order=order, trend="c")
            fitted = model.fit(method_kwargs={"warn_convergence": False})
            fc = fitted.get_forecast(horizon)
            mean = np.asarray(fc.predicted_mean, dtype=float)
            se = np.asarray(fc.se_mean, dtype=float)
            z = z_normal(quantiles)
            return mean[:, None] + se[:, None] * z[None, :]
        except Exception:
            return _fallback(y, horizon, quantiles)


def _pick_order(y: np.ndarray) -> tuple[int, int, int]:
    """Tiny AIC grid search over (p, d, q) - cheap and robust enough for v1."""
    try:
        from statsmodels.tsa.arima.model import ARIMA

        best, best_aic = (1, 1, 0), float("inf")
        for p in (0, 1, 2):
            for d in (0, 1):
                for q in (0, 1):
                    try:
                        fit = ARIMA(y, order=(p, d, q)).fit(method_kwargs={"warn_convergence": False})
                        if fit.aic < best_aic:
                            best, best_aic = (p, d, q), fit.aic
                    except Exception:
                        continue
        return best
    except Exception:
        return (1, 1, 0)


def _fallback(y: np.ndarray, horizon: int, quantiles: list[float]) -> np.ndarray:
    from prediction_engine.models.baseline import NaiveForecaster

    return NaiveForecaster().forecast_quantiles(y, horizon, quantiles)
