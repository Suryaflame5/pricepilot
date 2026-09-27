"""Forecast model interface.

Every model produces a quantile path of shape (horizon, len(quantiles)):
the probabilistic layer feeds on these. Models that cannot beat the naive
baseline on out-of-sample data are excluded at ensemble-fit time.
"""

from abc import ABC, abstractmethod

import numpy as np

QUANTILES = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]


class ForecastModel(ABC):
    name: str = "base"
    is_cheap: bool = True  # cheap models are refit per fold in backtests

    @abstractmethod
    def forecast_quantiles(
        self,
        y: np.ndarray,
        horizon: int,
        quantiles: list[float] | None = None,
    ) -> np.ndarray:
        """Return array of shape (horizon, len(quantiles))."""
        raise NotImplementedError


def _residual_quantiles(
    point: np.ndarray,
    residuals: np.ndarray,
    quantiles: list[float],
    horizon_scaling: bool = True,
) -> np.ndarray:
    """Quantile paths from point forecast + empirical residual distribution.

    Multi-step uncertainty is scaled by sqrt(h): for a random walk the
    h-step forecast error variance grows linearly with h, so naive/MA/ES
    intervals widen with the horizon instead of staying one-step tight.
    """
    q = np.quantile(residuals, quantiles)  # shape (nq,)
    if horizon_scaling:
        h = np.arange(1, len(point) + 1, dtype=float)
        q = q[None, :] * np.sqrt(h)[:, None]
    return point[:, None] + q


def z_normal(quantiles: list[float]) -> np.ndarray:
    from scipy.stats import norm

    return norm.ppf(quantiles)
