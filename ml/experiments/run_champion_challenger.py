"""Champion/challenger experiment runner (blueprint V1.1 ML ops).

Trains candidate variants on the same series, evaluates both via walk-forward
backtest on IDENTICAL folds, and applies the promotion gate. Never promotes on
a different data split than the incumbent was evaluated on.

Run: python -m ml.experiments.run_champion_challenger --series-db <sqlite> --challenger-gbm
     python -m ml.experiments.run_champion_challenger --variant <uuid> --challenger-gbm
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from prediction_engine.models.base import QUANTILES
from prediction_engine.models.baseline import (
    ExponentialSmoothingForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
)
from prediction_engine.models.statistical import ARIMAForecaster
from prediction_engine.registry import ModelRegistry, ModelRegistryEntry, evaluate_promotion

REGISTRY_DIR = Path(os.getenv("MODEL_REGISTRY_DIR", "ml/model_registry"))
DATABASE_URL = os.getenv("DATABASE_URL", None)

BASE_MODELS = [
    NaiveForecaster(),
    MovingAverageForecaster(window=7),
    ExponentialSmoothingForecaster(alpha=0.3),
    SeasonalNaiveForecaster(period=7),
    ARIMAForecaster(),
]


def _challenger_models(with_gbm: bool, y: np.ndarray):
    if not with_gbm:
        return list(BASE_MODELS)
    from prediction_engine.models.gbm import fit_gbm_models, fit_horizons

    return [fit_gbm_models(y, fit_horizons(30))]


def _series_from_db(variant_id: uuid.UUID) -> pd.Series:
    import sqlalchemy as sa

    from database.models import Listing, PriceObservation, ProductVariant
    from database.session import create_engine, create_session_factory, init_db

    async def load():
        engine = create_engine(DATABASE_URL)
        await init_db(engine)
        factory = create_session_factory(engine)
        async with factory() as db:
            stmt = (
                sa.select(PriceObservation.observed_at, PriceObservation.effective_price)
                .join(Listing, Listing.id == PriceObservation.listing_id)
                .where(Listing.product_variant_id == variant_id)
                .order_by(PriceObservation.observed_at)
            )
            rows = (await db.execute(stmt)).all()
        await engine.dispose()
        if not rows:
            raise SystemExit("no observations for variant")
        idx = pd.DatetimeIndex([r[0] for r in rows])
        return pd.Series([float(r[1]) for r in rows], index=idx)

    return asyncio.run(load())


def _make_bundle(result, category: str | None) -> dict:
    from prediction_engine.calibration import expected_calibration_error

    ece = None
    if result.prob_outcome:
        probs = np.asarray([p for p, _ in result.prob_outcome])
        outcomes = np.asarray([o for _, o in result.prob_outcome])
        ece = expected_calibration_error(probs, outcomes)
    per_horizon = {}
    for h, m in result.metrics.items():
        per_horizon[h] = m
    cov = result.coverage_90
    da_vals = [m["directional_accuracy"] for m in result.metrics.values() if m.get("directional_accuracy") == m.get("directional_accuracy")]
    st_vals = [m["stability"] for m in result.metrics.values() if m.get("stability") == m.get("stability")]
    overall = {
        "mae": float(np.mean([m["mae"] for m in result.metrics.values()])) if result.metrics else None,
        "quantile_loss_50": (
            float(np.mean([m["quantile_loss_50"] for m in result.metrics.values()])) if result.metrics else None
        ),
        "ece": ece,
        "coverage_abs_err": float(abs(np.nanmean(list(cov.values())) - 0.9)) if cov else None,
        "directional_accuracy": float(np.mean(da_vals)) if da_vals else None,
        "stability": float(np.mean(st_vals)) if st_vals else None,
        "n": result.samples,
    }
    return {"overall": overall, "per_horizon": per_horizon, "category": category}


def _series_from_csv(path: str) -> pd.Series:
    df = pd.read_csv(path)
    time_col = "t" if "t" in df.columns else "date" if "date" in df.columns else df.columns[0]
    price_col = "price" if "price" in df.columns else "effective_price" if "effective_price" in df.columns else df.columns[1]
    df[time_col] = pd.to_datetime(df[time_col])
    return df.set_index(time_col)[price_col].astype(float).sort_index()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", type=uuid.UUID, default=None)
    parser.add_argument("--series-csv", default=None, help="CSV with t,price columns for testing")
    parser.add_argument("--challenger-gbm", action="store_true", help="challenger = GBM quantile model")
    parser.add_argument("--promote", action="store_true", help="apply the promotion gate after evaluation")
    args = parser.parse_args()

    if args.variant and DATABASE_URL:
        series = _series_from_db(args.variant)
    elif args.series_csv:
        series = _series_from_csv(args.series_csv)
    else:
        rng = np.random.default_rng(11)
        n = 400
        y = 1000 * (1 + np.cumsum(rng.normal(0, 0.004, n)))
        series = pd.Series(y, index=pd.date_range("2025-01-01", periods=n, freq="D"))
        print("no input provided; using synthetic 400-obs series")

    from prediction_engine.backtesting import walk_forward_backtest

    y = series.dropna().to_numpy(dtype=float)
    champion_models = BASE_MODELS
    champion_res = walk_forward_backtest(y, 30, champion_models, n_folds=12, heavy=True)
    champion_bundle = _make_bundle(champion_res, None)

    challenger_models = _challenger_models(args.challenger_gbm, y)
    challenger_res = walk_forward_backtest(y, 30, challenger_models, n_folds=12, heavy=True)
    challenger_bundle = _make_bundle(challenger_res, None)

    print("=== champion (ensemble v1) ===")
    print(json.dumps(champion_bundle, indent=2, default=str))
    print("=== challenger ===")
    print(json.dumps(challenger_bundle, indent=2, default=str))

    verdict = evaluate_promotion(champion_bundle, challenger_bundle)
    print("=== promotion gate ===")
    print("promote:", verdict.promote)
    print("reasons:", verdict.reasons)
    print("improved:", verdict.scores.get("improved", []))

    if args.promote:
        registry = ModelRegistry(REGISTRY_DIR)
        champ = registry.get("champion-ensemble-v1")
        if champ is None:
            registry.register(
                ModelRegistryEntry(
                    model_id="champion-ensemble-v1",
                    name="ensemble v1",
                    status="CHAMPION",
                    model_type="ensemble",
                    metrics=champion_bundle,
                )
            )
        registry.register(
            ModelRegistryEntry(
                model_id="challenger-gbm-v1" if args.challenger_gbm else "challenger-baseline-v1",
                name="GBM quantile challenger" if args.challenger_gbm else "baseline challenger",
                status="CANDIDATE",
                model_type="gbm" if args.challenger_gbm else "ensemble",
                metrics=challenger_bundle,
            )
        )
        result = registry.promote(
            "challenger-gbm-v1" if args.challenger_gbm else "challenger-baseline-v1",
            champion_id="champion-ensemble-v1",
            notes="run_champion_challenger evaluation",
        )
        print("promotion result:", result.promote, result.reasons)


if __name__ == "__main__":
    main()
