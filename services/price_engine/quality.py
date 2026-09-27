"""Observation quality scoring + validation.

Quality score (0..1) weights:
    source_reliability   0.30   (collector provenance; feeds > pages > unknown)
    match_confidence     0.20   (how sure we are of product identity)
    price_validity       0.25   (sane price, within MRP bounds, parseable)
    availability_validity 0.15  (price present iff in stock; known states)
    freshness            0.10   (collected_at close to now)

Trust tiers: >=0.80 TRUSTED, >=0.55 REVIEW, else QUARANTINED.
The tier gates what forecasters may consume (TRUSTED directly, REVIEW after
verification/anomaly veto, QUARANTINED never).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SOURCE_RELIABILITY: dict[str, float] = {
    "feed": 1.0,      # official API/feed
    "page": 0.75,     # permitted structured-data extraction
    "mock": 0.9,      # dev/CI surrogate
    "manual": 0.7,    # operator-entered
}
DEFAULT_SOURCE_RELIABILITY = 0.4

WEIGHTS = {
    "source": 0.30,
    "match": 0.20,
    "price_validity": 0.25,
    "availability_validity": 0.15,
    "freshness": 0.10,
}

FRESHNESS_MAX_MINUTES = 6 * 60  # older than this starts to decay

TIER_TRUSTED = 0.80
TIER_REVIEW = 0.55


@dataclass
class QualityVerdict:
    score: float = 0.0
    tier: str = "QUARANTINED"  # TRUSTED / REVIEW / QUARANTINED
    components: dict[str, float] = field(default_factory=dict)
    validation_errors: dict[str, str] = field(default_factory=dict)
    valid: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "tier": self.tier,
            "components": self.components,
            "validation_errors": self.validation_errors,
            "valid": self.valid,
        }


def validate_state(state: dict[str, Any]) -> dict[str, str]:
    """Structural/plausibility validation. Empty errors => valid."""
    errors: dict[str, str] = {}
    price = state.get("price")
    mrp = state.get("mrp")
    availability = str(state.get("availability") or "IN_STOCK")

    if price is None:
        if availability == "IN_STOCK":
            errors["price_missing"] = "in-stock observation without a price"
    elif price <= 0:
        errors["price_nonpositive"] = f"price {price} <= 0"
    elif mrp is not None and mrp > 0 and price > mrp * 2.5:
        errors["price_exceeds_mrp"] = f"price {price} > 2.5x mrp {mrp}"

    if mrp is not None and mrp < 0:
        errors["mrp_negative"] = f"mrp {mrp} < 0"

    if availability not in ("IN_STOCK", "OUT_OF_STOCK", "PRE_ORDER"):
        errors["availability_unknown"] = f"unknown availability {availability}"

    for field_name in ("shipping", "coupon_discount", "bank_discount"):
        v = state.get(field_name)
        if v is not None and v < 0:
            errors[f"{field_name}_negative"] = f"{field_name} {v} < 0"
    return errors


def _freshness_component(collected_at: datetime | None, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    if collected_at is None:
        return 0.0
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=timezone.utc)
    age_min = (now - collected_at).total_seconds() / 60.0
    if age_min <= 0:
        return 1.0
    return max(0.0, 1.0 - age_min / FRESHNESS_MAX_MINUTES)


def score_observation(
    state: dict[str, Any],
    *,
    source_mode: str | None = None,
    collected_at: datetime | None = None,
    match_confidence: float | None = None,
    now: datetime | None = None,
) -> QualityVerdict:
    errors = validate_state(state)
    valid = not errors
    availability = str(state.get("availability") or "IN_STOCK")

    components: dict[str, float] = {
        "source": SOURCE_RELIABILITY.get(source_mode or "", DEFAULT_SOURCE_RELIABILITY),
        "match": match_confidence if match_confidence is not None else 0.0,
        "price_validity": 0.0,
        "availability_validity": 1.0,
        "freshness": _freshness_component(collected_at, now),
    }

    if valid:
        price = state.get("price")
        mrp = state.get("mrp")
        price_score = 1.0
        if mrp is not None and mrp > 0 and price is not None:
            ratio = price / mrp
            price_score = 1.0 if ratio <= 1.0 else max(0.0, 1.0 - (ratio - 1.0))
        elif price is None:
            price_score = 0.0
        components["price_validity"] = price_score
        components["availability_validity"] = 1.0 if availability == "IN_STOCK" else 0.7
    else:
        components["price_validity"] = 0.0
        components["availability_validity"] = 0.0

    score = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    tier = (
        "TRUSTED" if score >= TIER_TRUSTED
        else "REVIEW" if score >= TIER_REVIEW
        else "QUARANTINED"
    )
    return QualityVerdict(score=score, tier=tier, components=components, validation_errors=errors, valid=valid)
