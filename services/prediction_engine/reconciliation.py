"""Cross-retailer reconciliation (blueprint: P_market(t) = P_retailer(t) - R_retailer(t)).

Retailer prices = market price + retailer offset. The market series is built
from concurrent retailer observations (median across listings per timestamp),
and each retailer's offset is estimated on a rolling window. Retailer forecasts
then come from a market-level forecast plus the (stable) retailer offset,
which is more accurate than forecasting each noisy retailer series alone.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

OFFSET_WINDOW_DAYS = 30
MIN_OVERLAP = 3


@dataclass
class ReconciliationResult:
    market: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    offsets: dict[str, float] = field(default_factory=dict)
    retailer_series: dict[str, pd.Series] = field(default_factory=dict)
    overlap: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "market_points": len(self.market),
            "offsets": {k: round(v, 2) for k, v in self.offsets.items()},
            "overlap": self.overlap,
        }


def _align(series: dict[str, pd.Series]) -> pd.DataFrame:
    return pd.concat(
        {name: s.rename("price") for name, s in series.items()}, axis=1, sort=True
    )


def reconcile(series_by_retailer: dict[str, pd.Series], window_days: int = OFFSET_WINDOW_DAYS) -> ReconciliationResult:
    """Market series + per-retailer offsets from overlapping timestamps.

    series_by_retailer: retailer_name -> time-indexed price series.
    """
    result = ReconciliationResult(retailer_series=series_by_retailer)
    if not series_by_retailer:
        return result

    df = _align(series_by_retailer).dropna(how="all").sort_index()
    if df.empty:
        return result

    # market = median across retailers at each timestamp
    result.market = df.median(axis=1, skipna=True)

    # offsets over the overlap window
    now = df.index.max()
    start = now - pd.Timedelta(days=window_days)
    recent = df[df.index >= start]
    market_recent = result.market[result.market.index >= start]
    for name, col in recent.items():
        overlap = col.notna() & market_recent.notna()
        if int(overlap.sum()) >= MIN_OVERLAP:
            diff = (col[overlap] - market_recent[overlap]).mean()
            result.offsets[name] = float(diff)
            result.overlap[name] = int(overlap.sum())

    # recenter so median offset = 0: the market series then represents the
    # TYPICAL retailer and offsets measure relative position (robust when few
    # retailers exist; the median-of-2 midpoint bias is absorbed into market).
    if result.offsets:
        med = float(np.median(list(result.offsets.values())))
        if med != 0.0:
            result.offsets = {k: v - med for k, v in result.offsets.items()}
    return result


def forecast_retailer(
    market_forecast: np.ndarray,
    market_price: float,
    offset: float,
    offset_n: int,
    min_offset_samples: int = MIN_OVERLAP,
) -> np.ndarray:
    """Retailer forecast = market forecast + offset (when offset is estimated)."""
    offset_used = offset if offset_n >= min_offset_samples else 0.0
    return np.asarray(market_forecast, dtype=float) + offset_used


def market_from_listings(
    df: pd.DataFrame,
    price_col: str = "effective_price",
    time_col: str = "t",
    retailer_col: str = "retailer",
) -> dict[str, pd.Series]:
    """Group a long-format observation frame into per-retailer series + returns them."""
    out: dict[str, pd.Series] = {}
    for name, group in df.groupby(retailer_col):
        s = group.sort_values(time_col).set_index(time_col)[price_col].astype(float)
        s = s[~s.index.duplicated(keep="last")]
        out[str(name)] = s
    return out
