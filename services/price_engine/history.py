"""History access: load series from the database, resample, compute stats."""

import uuid
from datetime import timedelta
from typing import Awaitable, Callable

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Listing, PriceObservation, Retailer

SeriesLoader = Callable[[uuid.UUID, str | None], Awaitable[pd.Series]]


async def load_listing_series(
    session: AsyncSession,
    listing_id: uuid.UUID,
    field: str = "effective_price",
    since_days: int | None = None,
) -> pd.Series:
    """Load a listing's price history as a time-indexed pd.Series."""
    stmt = select(PriceObservation.observed_at, getattr(PriceObservation, field)).where(
        PriceObservation.listing_id == listing_id,
        PriceObservation.observed_at.isnot(None),
    )
    if since_days:
        stmt = stmt.where(PriceObservation.observed_at >= pd.Timestamp.utcnow() - pd.Timedelta(days=since_days))
    stmt = stmt.order_by(PriceObservation.observed_at)

    rows = (await session.execute(stmt)).all()
    if not rows:
        return pd.Series(dtype=float)

    index = pd.DatetimeIndex([r[0] for r in rows]).tz_convert(None) if rows[0][0].tzinfo else pd.DatetimeIndex([r[0] for r in rows])
    values = [float(r[1]) for r in rows if r[1] is not None]
    if not values:
        return pd.Series(dtype=float)
    return pd.Series(values, index=index[: len(values)])


async def load_variant_series(
    session: AsyncSession,
    variant_id: uuid.UUID,
    field: str = "effective_price",
    since_days: int | None = None,
) -> pd.Series:
    """Cheapest-active-listing price trajectory for a variant (market view)."""
    stmt = (
        select(Listing.id)
        .where(Listing.product_variant_id == variant_id, Listing.active.is_(True))
    )
    listing_ids = [r[0] for r in (await session.execute(stmt)).all()]
    if not listing_ids:
        return pd.Series(dtype=float)

    obs_stmt = (
        select(PriceObservation.observed_at, getattr(PriceObservation, field))
        .where(PriceObservation.listing_id.in_(listing_ids))
    )
    if since_days:
        obs_stmt = obs_stmt.where(
            PriceObservation.observed_at >= pd.Timestamp.utcnow() - pd.Timedelta(days=since_days)
        )
    rows = (await session.execute(obs_stmt)).all()
    if not rows:
        return pd.Series(dtype=float)

    df = pd.DataFrame(
        {"t": [r[0] for r in rows], "p": [float(r[1]) for r in rows if r[1] is not None]}
    ).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    df["t"] = pd.to_datetime(df["t"])
    series = df.sort_values("t").groupby("t")["p"].min()  # market = cheapest active listing
    series.index = series.index.tz_convert(None) if series.index.tz is not None else series.index
    return series


def resample_series(series: pd.Series, rule: str = "1d") -> pd.Series:
    if series.empty:
        return series
    return series.resample(rule).mean().dropna()


def series_to_points(series: pd.Series) -> list[dict]:
    return [
        {"t": ts.to_pydatetime().isoformat() if hasattr(ts, "to_pydatetime") else str(ts), "price": float(v)}
        for ts, v in series.items()
    ]


def price_stats(series: pd.Series, now_ts=None) -> dict:
    """Blueprint section 5 feature block: means/min/max over windows + percentile."""
    if series.empty:
        return {}
    now = pd.Timestamp.utcnow()
    if series.index.tz is None:
        now = now.tz_localize(None)
    out: dict = {"current_price": float(series.iloc[-1])}

    def win(days: int) -> pd.Series:
        return series[series.index >= now - pd.Timedelta(days=days)]

    for days in (1, 7, 30, 90):
        w = win(days)
        out[f"mean_{days}d"] = round(float(w.mean()), 2) if len(w) else None
        out[f"min_{days}d"] = round(float(w.min()), 2) if len(w) else None
        out[f"max_{days}d"] = round(float(w.max()), 2) if len(w) else None

    w90 = win(90)
    cur = out["current_price"]
    out["price_percentile_90d"] = (
        round(float((w90 <= cur).mean()), 4) if len(w90) > 1 else None
    )
    out["observations_90d"] = int(len(w90))
    return out
