"""Feature engine (blueprint section 5).

Computes the full feature block: price, relative, retailer, temporal,
lifecycle and event features. v1 uses it for statistics and reporting;
GBM v2 training will consume the same builder.
"""

from datetime import datetime

import numpy as np
import pandas as pd

INDIAN_FESTIVALS = {
    (1, 26): "republic_day",
    (3, 25): "holi",
    (8, 15): "independence_day",
    (10, 2): "gandhi_jayanti",
    (11, 1): "diwali_week",
    (12, 25): "christmas",
}
BLACK_FRIDAY_WEEK = 47  # iso week


def price_features(series: pd.Series) -> dict:
    """Means/min/max/velocity/acceleration/volatility over windows."""
    out: dict = {}
    if series.empty:
        return out
    now = series.index[-1]
    cur = float(series.iloc[-1])
    out["current_price"] = cur

    for days in (1, 6, 7, 30, 90, 365):
        w = series[series.index >= now - pd.Timedelta(days=days)]
        out[f"mean_{days}d"] = round(float(w.mean()), 2) if len(w) else None
        if days >= 7:
            out[f"min_{days}d"] = round(float(w.min()), 2) if len(w) else None
            out[f"max_{days}d"] = round(float(w.max()), 2) if len(w) else None

    if len(series) >= 8:
        rets = series.pct_change().dropna()
        out["price_velocity"] = round(float(series.iloc[-1] / series.iloc[-8] - 1), 4)
        out["price_acceleration"] = round(float(rets.diff().iloc[-1]), 4)
        out["price_volatility"] = round(float(rets.std(ddof=1)), 4)
        out["price_percentile_90d"] = round(float((series.iloc[-90:] <= cur).mean()), 4)
    return out


def relative_features(series: pd.Series, feats: dict) -> dict:
    out: dict = {}
    if series.empty:
        return out
    cur = feats.get("current_price")
    for days in (7, 30, 90):
        mean = feats.get(f"mean_{days}d")
        if cur and mean:
            out[f"price_vs_{days}d_average"] = round(cur / mean - 1, 4)
    return out


def temporal_features(ts: datetime | pd.Timestamp) -> dict:
    out = {
        "hour": ts.hour,
        "day": ts.day,
        "weekday": ts.weekday(),
        "week": ts.isocalendar().week if hasattr(ts, "isocalendar") else ts.week,
        "month": ts.month,
        "quarter": (ts.month - 1) // 3 + 1,
        "holiday": 0,
        "festival": 0,
        "payday_period": 1 if ts.day >= 25 or ts.day <= 2 else 0,
    }
    if (ts.month, ts.day) in INDIAN_FESTIVALS:
        out["holiday"] = 1
        out["festival"] = 1
    if ts.isocalendar().week == BLACK_FRIDAY_WEEK:
        out["festival"] = 1
    return out


def lifecycle_features(now: datetime, launched_at: datetime | None = None) -> dict:
    if not launched_at:
        return {"days_since_launch": None, "product_age_days": None}
    days = max(0, (now - launched_at).total_seconds() // 86400)
    return {"days_since_launch": int(days), "product_age_days": int(days)}


def event_features(upcoming: list) -> list[dict]:
    """known-future features: one-hot style flags + days-until for each event."""
    out = []
    for ev in upcoming:
        if not ev.starts_at:
            continue
        days = max(0, int((ev.starts_at - datetime.now(ev.starts_at.tzinfo)).total_seconds() // 86400))
        out.append({"event_type": ev.event_type, "name": ev.name, "days_until": days})
    return out


def build_feature_row(
    series: pd.Series,
    ts: datetime | pd.Timestamp,
    upcoming_events: list | None = None,
    launched_at: datetime | None = None,
) -> dict:
    feats = price_features(series)
    feats.update(relative_features(series, feats))
    feats.update(temporal_features(ts))
    feats.update(lifecycle_features(ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts, launched_at))
    feats["upcoming_events"] = event_features(upcoming_events or [])
    return feats
