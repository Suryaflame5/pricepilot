"""Observation validation: reject garbage before it pollutes the series.

Rules:
  - effective price must be positive and finite
  - effective price must not exceed MRP by more than a tolerance
  - availability must be a known value or None
"""

from dataclasses import dataclass
from math import isfinite

VALID_AVAILABILITY = {"IN_STOCK", "OUT_OF_STOCK", "BACKORDER", "PREORDER", None}


class ValidationError(Exception):
    pass


@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str]


def validate_observation(obs) -> ValidationResult:
    reasons: list[str] = []
    p = obs.effective_price

    if p is None or not isfinite(p) or p <= 0:
        reasons.append("effective price must be positive and finite")

    if obs.mrp is not None and obs.mrp > 0 and p > obs.mrp * 1.05:
        reasons.append("effective price exceeds MRP by more than 5%")

    if obs.availability not in VALID_AVAILABILITY:
        reasons.append(f"unknown availability: {obs.availability}")

    if reasons:
        raise ValidationError("; ".join(reasons))
    return ValidationResult(ok=True, reasons=[])
