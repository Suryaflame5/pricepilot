"""Change detection between consecutive observations -> typed events.

Policy mirrors packages.events.CHANGE_EVENT_THRESHOLDS so consumers see one truth:
    price.changed        any price move
    price.dropped        >= drop_pct (2%) below previous
    price.spike          >= spike_pct (5%) above previous within a short window
    stock.changed        availability transition
    seller.changed       seller identity change
    promotion.started    coupon appeared (0 -> >0)
    promotion.ended      coupon disappeared (>0 -> 0)
"""

from dataclasses import dataclass, field
from typing import Any

from packages.events.bus import CHANGE_EVENT_THRESHOLDS


@dataclass
class ChangeEvent:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"event_type": self.event_type, "payload": self.payload}


def _state_of(obs: Any) -> dict[str, Any]:
    """Extract canonical comparison state from a PriceObservation OR dict."""
    if isinstance(obs, dict):
        return obs
    return {
        "price": float(obs.price) if obs.price is not None else None,
        "coupon_discount": float(obs.coupon_discount or 0.0),
        "availability": obs.availability,
        "seller_name": getattr(obs, "seller_name", None),
        "observed_at": obs.observed_at,
    }


def detect_changes(previous: Any, current: Any) -> list[ChangeEvent]:
    prev = _state_of(previous)
    curr = _state_of(current)
    events: list[ChangeEvent] = []

    p_price = prev.get("price")
    c_price = curr.get("price")
    if c_price is not None and p_price is not None and p_price > 0:
        pct = (c_price - p_price) / p_price
        if abs(pct) > 1e-9:
            base = {
                "from": p_price,
                "to": c_price,
                "pct_change": round(pct, 6),
                "observed_at": str(curr.get("observed_at") or ""),
            }
            events.append(ChangeEvent("price.changed", dict(base)))
            if pct <= -CHANGE_EVENT_THRESHOLDS["drop_pct"]:
                events.append(ChangeEvent("price.dropped", dict(base)))
            elif pct >= CHANGE_EVENT_THRESHOLDS["spike_pct"]:
                events.append(ChangeEvent("price.spike", dict(base)))

    p_avail = prev.get("availability")
    c_avail = curr.get("availability")
    if p_avail and c_avail and p_avail != c_avail:
        events.append(
            ChangeEvent("stock.changed", {"from": p_avail, "to": c_avail})
        )

    p_seller = prev.get("seller_name")
    c_seller = curr.get("seller_name")
    if p_seller and c_seller and p_seller != c_seller:
        events.append(
            ChangeEvent("seller.changed", {"from": p_seller, "to": c_seller})
        )

    p_coupon = prev.get("coupon_discount") or 0.0
    c_coupon = curr.get("coupon_discount") or 0.0
    if p_coupon <= 0 < c_coupon:
        events.append(ChangeEvent("promotion.started", {"coupon_discount": c_coupon}))
    elif p_coupon > 0 >= c_coupon:
        events.append(ChangeEvent("promotion.ended", {"coupon_discount": c_coupon}))

    return events
