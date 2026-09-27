"""Price normalization: compute the canonical effective price.

effective_price = price - coupon_discount - bank_discount + shipping
"""

from dataclasses import dataclass

from price_engine.validator import ValidationError, validate_observation


@dataclass
class NormalizedObservation:
    price: float
    mrp: float | None
    shipping: float
    coupon_discount: float
    bank_discount: float
    effective_price: float
    availability: str | None


def compute_effective_price(
    price: float,
    coupon_discount: float = 0,
    bank_discount: float = 0,
    shipping: float = 0,
) -> float:
    return round(float(price) - float(coupon_discount) - float(bank_discount) + float(shipping), 2)


def normalize_observation(
    price: float,
    mrp: float | None = None,
    shipping: float = 0,
    coupon_discount: float = 0,
    bank_discount: float = 0,
    availability: str | None = "IN_STOCK",
) -> NormalizedObservation:
    """Normalize + validate a raw scrape into a canonical observation."""
    try:
        effective = compute_effective_price(price, coupon_discount, bank_discount, shipping)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"non-numeric price fields: {exc}") from exc

    obs = NormalizedObservation(
        price=round(float(price), 2),
        mrp=round(float(mrp), 2) if mrp is not None else None,
        shipping=round(float(shipping), 2),
        coupon_discount=round(float(coupon_discount), 2),
        bank_discount=round(float(bank_discount), 2),
        effective_price=effective,
        availability=availability,
    )
    validate_observation(obs)
    return obs
