"""Monitoring routes: drift, coverage, model registry, calibration summary.

These are the reliability-contract surfaces: they report MEASURED behavior
(coverage, ECE, drift) rather than claims.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db
from database.models import (
    Prediction,
    PredictionOutcome,
    PriceObservation,
    Product,
    ProductVariant,
)
from prediction_engine.calibration import CalibrationStore
from prediction_engine.drift import detect_feature_drift, evaluate_coverage
from prediction_engine.registry import ModelRegistry
from price_engine.history import load_variant_series
from schemas.monitoring import (  # noqa: E402
    CalibrationSummaryOut,
    CalibrationCurveOut,
    CoverageOut,
    DriftOut,
    LedgerOut,
    LedgerRowOut,
    RegistryEntryOut,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/ledger", response_model=LedgerOut)
async def prediction_ledger(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Measured per-category/horizon forecast performance from resolved outcomes.

    The reliable truth: this table only counts outcomes that actually resolved
    against observations - no self-reported performance. Empty when the ledger
    has not elapsed (run ml.ledger.resolve_outcomes after horizons pass).
    """
    stmt = (
        select(
            Product.category,
            Prediction.horizon_hours,
            Prediction.model_version,
            PredictionOutcome.in_interval,
            PredictionOutcome.error_abs,
            PredictionOutcome.error_median,
            Prediction.target_price,
            Prediction.probability_below_target,
            PredictionOutcome.actual_effective_price,
        )
        .join(ProductVariant, Prediction.product_variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
    )
    if category:
        stmt = stmt.where(Product.category == category)
    rows = (await db.execute(stmt)).all()

    groups: dict[tuple[str, int], list] = {}
    for cat, hours, model, in_interval, err_abs, err_med, target, prob, actual in rows:
        key = (cat or "unknown", (hours or 0) // 24)
        groups.setdefault(key, []).append(
            (model, in_interval, err_abs, err_med, target, prob, actual)
        )

    out = []
    for (cat, days), items in sorted(groups.items()):
        intervals = [i for _, i, *_ in items if i is not None]
        abs_err = [item[2] for item in items if item[2] is not None]
        med_err = [item[3] for item in items if item[3] is not None]
        briers = []
        for _, _, _, _, target, prob, actual in items:
            if target is not None and prob is not None and actual is not None:
                hit = 1.0 if actual <= target else 0.0
                briers.append((prob - hit) ** 2)
        out.append(
            LedgerRowOut(
                category=cat,
                horizon_days=days,
                n=len(items),
                coverage_90=round(sum(intervals) / len(intervals), 4) if intervals else None,
                mae=round(sum(abs_err) / len(abs_err), 2) if abs_err else None,
                median_error=round(sum(med_err) / len(med_err), 2) if med_err else None,
                brier=round(sum(briers) / len(briers), 4) if briers else None,
                model_version=items[-1][0] if items else None,
            )
        )

    total = (
        await db.execute(select(func.count()).select_from(Prediction))
    ).scalar_one()
    outcomes = (
        await db.execute(select(func.count()).select_from(PredictionOutcome))
    ).scalar_one()
    return LedgerOut(rows=out, total_predictions=int(total), outcomes_recorded=int(outcomes))


@router.get("/drift", response_model=DriftOut)
async def feature_drift(
    variant_id: uuid.UUID,
    baseline_days: int = Query(90, ge=14, le=730),
    recent_days: int = Query(7, ge=2, le=30),
    db: AsyncSession = Depends(get_db),
):
    series = await load_variant_series(db, variant_id, since_days=baseline_days)
    if len(series) < 15:
        raise HTTPException(404, "insufficient history for drift detection")
    baseline = series.iloc[: -recent_days].to_numpy(dtype=float)
    recent = series.iloc[-recent_days:].to_numpy(dtype=float)
    report = detect_feature_drift(baseline, recent)
    return DriftOut(drifted=report.drifted, reasons=report.reasons, details=report.details)


@router.get("/coverage", response_model=CoverageOut)
async def coverage(
    target_level: float = Query(0.90, ge=0.5, le=0.99),
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(PredictionOutcome.in_interval)
        .where(PredictionOutcome.in_interval.isnot(None))
        .order_by(PredictionOutcome.created_at.desc())
        .limit(limit)
    )
    flags = [bool(r[0]) for r in (await db.execute(stmt)).all()]
    return CoverageOut(**evaluate_coverage(flags, level=target_level))


@router.get("/registry", response_model=list[RegistryEntryOut])
async def model_registry():
    registry = ModelRegistry(settings.model_registry_dir)
    return [
        RegistryEntryOut(
            model_id=e.model_id,
            name=e.name,
            status=e.status,
            model_type=e.model_type,
            category=e.category,
            horizon_hours=e.horizon_hours,
            metrics=e.metrics,
            promoted_at=e.promoted_at,
            retired_at=e.retired_at,
        )
        for e in registry.list()
    ]


@router.get("/calibration", response_model=CalibrationSummaryOut)
async def calibration_summary():
    store = CalibrationStore(settings.calibration_store_dir)
    return CalibrationSummaryOut(
        curves=[
            CalibrationCurveOut(key=c["key"], n_pairs=c.get("n_pairs"), ece=c.get("ece"))
            for c in store.summary().get("curves", [])
        ]
    )
