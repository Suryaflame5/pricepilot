"""Continuous backtesting CLI (blueprint section 20, V1.1).

Loads variant histories from the database and runs walk-forward backtests,
then refreshes:
  - hierarchical calibration curves (category:horizon:regime:retailer hierarchy)
  - regime-conditional conformal residual buckets
  - champion registry metrics (for promotion decisions)
  - drift + coverage monitoring report

Run: python -m ml.backtesting.run [--variant UUID] [--heavy]
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from database.models import ProductVariant
from database.session import create_engine, create_session_factory, init_db
from prediction_engine.backtesting import walk_forward_backtest
from prediction_engine.calibration import CalibrationStore, MIN_CALIBRATION_PAIRS
from prediction_engine.conformal import RegimeConformalStore
from prediction_engine.models.base import QUANTILES
from prediction_engine.models.baseline import (
    ExponentialSmoothingForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
)
from prediction_engine.models.statistical import ARIMAForecaster
from prediction_engine.registry import ModelRegistry, ModelRegistryEntry
from price_engine.history import load_variant_series

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pricepilot:pricepilot@localhost:5432/pricepilot",
)
REGISTRY_DIR = Path(os.getenv("MODEL_REGISTRY_DIR", "ml/model_registry"))
CALIBRATION_DIR = Path(os.getenv("CALIBRATION_STORE_DIR", "ml/model_registry/calibration"))
CONFORMAL_DIR = Path(os.getenv("CONFORMAL_STORE_DIR", "ml/model_registry/conformal"))
REPORT_DIR = Path(os.getenv("MONITORING_REPORT_DIR", "ml/model_registry/monitoring"))


def _models():
    return [
        NaiveForecaster(),
        MovingAverageForecaster(window=7),
        ExponentialSmoothingForecaster(alpha=0.3),
        SeasonalNaiveForecaster(period=7),
        ARIMAForecaster(),
    ]


async def backtest_variant(
    db: AsyncSession,
    variant_id: uuid.UUID,
    heavy: bool,
    cal_pairs: dict[str, list],
    residual_buckets: dict[int, dict[str, list]],
) -> dict | None:
    series = await load_variant_series(db, variant_id, since_days=730)
    if len(series) < 40:
        return None
    y = series.to_numpy(dtype=float)
    variant = (
        await db.execute(
            select(ProductVariant)
            .where(ProductVariant.id == variant_id)
            .options(selectinload(ProductVariant.product))
        )
    ).scalar_one_or_none()
    category = variant.product.category if variant and variant.product else None

    result = walk_forward_backtest(y, 30, _models(), n_folds=10, heavy=heavy)
    print(f"variant {variant_id} ({category}): folds={result.folds} samples={result.samples}")
    print(f"  90% coverage: {result.coverage_90} regimes: {result.regimes_seen}")

    for p, o in result.prob_outcome:
        cal_pairs[f"{category or 'default'}:{30 * 24}"].append((p, o))  # keys are HOURS (engine unit)
    for h, buckets in result.residual_buckets.items():
        for regime, resids in buckets.items():
            residual_buckets[h].setdefault(regime, []).extend(resids.tolist())

    return {
        "variant_id": str(variant_id),
        "category": category,
        "metrics": result.metrics,
        "coverage_90": result.coverage_90,
        "samples": result.samples,
        "folds": result.folds,
        "regimes_seen": result.regimes_seen,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", type=uuid.UUID, default=None)
    parser.add_argument("--heavy", action="store_true", help="include ARIMA/GBM in folds")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    await init_db(engine)
    factory = create_session_factory(engine)

    cal_pairs: dict[str, list] = defaultdict(list)
    residual_buckets: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    reports: list[dict] = []

    async with factory() as db:
        if args.variant:
            rep = await backtest_variant(db, args.variant, args.heavy, cal_pairs, residual_buckets)
            if rep:
                reports.append(rep)
        else:
            variants = (await db.execute(select(ProductVariant))).scalars().all()
            for v in variants:
                rep = await backtest_variant(db, v.id, args.heavy, cal_pairs, residual_buckets)
                if rep:
                    reports.append(rep)
    await engine.dispose()

    # 1) hierarchical calibration refresh (min-pairs guarded)
    cal_store = CalibrationStore(CALIBRATION_DIR)
    fitted: list[str] = []
    for key, pairs in sorted(cal_pairs.items()):
        if len(pairs) < MIN_CALIBRATION_PAIRS:
            continue
        probs = [p for p, _ in pairs]
        outcomes = [o for _, o in pairs]
        import numpy as np

        if cal_store.save_fit(np.asarray(probs), np.asarray(outcomes), key):
            fitted.append(key)
    print(f"calibration curves fitted: {fitted or 'none (insufficient pairs)'}")

    # 2) regime-conditional conformal buckets
    conf_store = RegimeConformalStore(CONFORMAL_DIR)
    conf_store.load()
    for h, buckets in residual_buckets.items():
        for regime, resids in buckets.items():
            conf_store.fit_bucket(h, regime, resids, 0.90)
    conf_store.save()
    print(f"conformal buckets updated for horizons {sorted(residual_buckets)}")

    # 3) champion metrics refresh for promotion decisions
    registry = ModelRegistry(REGISTRY_DIR)
    if reports:
        overall = _aggregate_metrics(reports)
        champion = registry.get_champion()
        entry = ModelRegistryEntry(
            model_id="pricepilot-v1.1.0",
            name="ensemble v1.1 (naive/MA/ES/seasonal/ARIMA)",
            status="CHAMPION" if champion is None else champion.status,
            model_type="ensemble",
            metrics=overall,
            features_version="v1.1",
            calibration_version="hierarchical-v1",
            conformal_version="regime-v1",
        )
        registry.register(entry)
        print(f"registry metrics updated: mae={overall.get('overall', {}).get('mae')}")

    # 4) monitoring report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "variants": len(reports),
        "calibration": cal_store.summary(),
        "conformal": conf_store.state(),
        "metrics": _aggregate_metrics(reports) if reports else {},
    }
    (REPORT_DIR / "continuous_backtest.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"monitoring report -> {REPORT_DIR / 'continuous_backtest.json'}")


def _aggregate_metrics(reports: list[dict]) -> dict:
    """Pool per-horizon metrics across variants into overall + per_horizon."""
    import numpy as np

    by_h: dict[str, list[dict]] = defaultdict(list)
    for rep in reports:
        for h, m in (rep.get("metrics") or {}).items():
            by_h[h].append(m)
    per_horizon: dict[str, dict] = {}
    total_n = 0
    mae_weighted = 0.0
    for h, metrics in by_h.items():
        mae = [m["mae"] for m in metrics]
        ql = [m["quantile_loss_50"] for m in metrics]
        da = [m["directional_accuracy"] for m in metrics if m.get("directional_accuracy") == m.get("directional_accuracy")]
        st = [m["stability"] for m in metrics if m.get("stability") == m.get("stability")]
        n = sum(m["n"] for m in metrics)
        total_n += n
        per_horizon[h] = {
            "mae": round(float(np.mean(mae)), 2),
            "quantile_loss_50": round(float(np.mean(ql)), 2),
            "directional_accuracy": round(float(np.mean(da)), 4) if da else None,
            "stability": round(float(np.mean(st)), 4) if st else None,
            "n": n,
        }
        mae_weighted += sum(m["mae"] * m["n"] for m in metrics)
    overall = {
        "mae": round(float(mae_weighted / total_n), 2) if total_n else None,
        "n": int(total_n),
    }
    return {"overall": overall, "per_horizon": per_horizon}


if __name__ == "__main__":
    asyncio.run(main())
