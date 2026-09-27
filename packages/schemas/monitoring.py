"""Monitoring API schemas: drift, coverage, registry, calibration."""

from pydantic import BaseModel


class DriftOut(BaseModel):
    drifted: bool
    reasons: list[str]
    details: dict


class CoverageOut(BaseModel):
    coverage: float | None = None
    n: int = 0
    target: float | None = None
    within_tolerance: bool | None = None
    drifted: bool | None = None


class RegistryEntryOut(BaseModel):
    model_id: str
    name: str
    status: str
    model_type: str | None = None
    category: str | None = None
    horizon_hours: int | None = None
    metrics: dict | None = None
    promoted_at: str | None = None
    retired_at: str | None = None


class CalibrationCurveOut(BaseModel):
    key: str
    n_pairs: int | None = None
    ece: float | None = None


class CalibrationSummaryOut(BaseModel):
    curves: list[CalibrationCurveOut]


class LedgerRowOut(BaseModel):
    """One row of the Prediction Ledger performance truth table."""
    category: str
    horizon_days: int
    n: int
    coverage_90: float | None = None      # measured interval hit-rate
    mae: float | None = None              # mean absolute median-error
    median_error: float | None = None
    brier: float | None = None            # probability below target vs actual
    model_version: str | None = None


class LedgerOut(BaseModel):
    rows: list[LedgerRowOut]
    total_predictions: int = 0
    outcomes_recorded: int = 0
