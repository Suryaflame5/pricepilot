"""Purchase provider registry (V1.2 P1).

Only retailer-permitted providers are registered. Today only the mock provider
exists; Amazon/Flipkart/Croma wrappers slot in here once official APIs/feeds
are approved. An unregistered retailer is a hard error - the purchase layer
NEVER falls back to a generic implementation.
"""

import uuid

from schemas.offer import Offer

from purchase.base import PurchaseError, PurchaseProvider


_MOCK_SESSIONS: dict[str, str] = {}  # provider session -> listing id (server-side)
_MOCK_ORDERS: dict[str, dict] = {}
_MOCK_SEQ = 0


class MockPurchaseProvider:
    """Deterministic provider for tests and local demos.

    State is server-side (module-level), exactly like a real retailer: a
    provider session id created by one instance is honoured by any other.
    Totals use the same arithmetic as the Offer plus a fixed tax rate so the
    'price verified immediately before purchase' invariant is testable.
    """

    name = "mock"
    retailer = "mock"
    TAX_RATE = 0.0

    def __init__(self) -> None:
        self._sessions = _MOCK_SESSIONS
        self._orders = _MOCK_ORDERS
        self._seq = 0

    async def create_session(self, offer: Offer) -> dict:
        session_id = f"mock-sess-{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = str(offer.listing_id)
        return {"session_id": session_id, "retailer": self.retailer}

    async def add_to_cart(self, provider_session_id: str, offer: Offer) -> dict:
        if provider_session_id not in self._sessions:
            raise PurchaseError("unknown provider session")
        return {"session_id": provider_session_id, "item_added": True}

    async def get_checkout_total(self, provider_session_id: str, offer: Offer) -> dict:
        if provider_session_id not in self._sessions:
            raise PurchaseError("unknown provider session")
        total = round(offer.expected_total * (1 + self.TAX_RATE), 2)
        return {"total": total, "delivery_estimate": _days(offer)}

    async def place_order(
        self,
        provider_session_id: str,
        offer: Offer,
        total: float,
        delivery_estimate: str | None = None,
    ) -> dict:
        if provider_session_id not in self._sessions:
            raise PurchaseError("unknown provider session")
        self._seq += 1
        ref = f"MOCK-{self._seq:06d}"
        self._orders[ref] = {"status": "TRACKING", "total": total}
        return {"order_ref": ref, "status": "TRACKING", "tracking_url": f"https://mock.retailer/tracking/{ref}"}

    async def get_order_status(self, order_ref: str) -> dict:
        order = self._orders.get(order_ref)
        if order is None:
            raise PurchaseError(f"unknown order {order_ref}")
        return {"status": order["status"], "detail": "order placed (mock)", "tracking_url": f"https://mock.retailer/tracking/{order_ref}"}


def _days(offer: Offer) -> str:
    if offer.delivery and offer.delivery.days:
        return f"{offer.delivery.days} business days"
    return "3-5 business days"


_BUILTINS: dict[str, type[PurchaseProvider]] = {
    "mock": MockPurchaseProvider,
}


def get_provider(retailer_name: str) -> PurchaseProvider:
    """Resolve a provider by retailer name. Unregistered -> hard error."""
    key = (retailer_name or "").strip().lower()
    cls = _BUILTINS.get(key)
    if cls is None:
        raise PurchaseError(
            f"no purchase provider for retailer '{retailer_name}'; "
            "only retailer-permitted integrations are enabled"
        )
    return cls()


def registered_providers() -> list[str]:
    return sorted(_BUILTINS)