"""PurchaseProvider protocol (V1.2 P1).

Only retailer-permitted integrations are instantiated here. The AI layer never
talks to a provider directly: it drives the ShoppingSession state machine via
the API, and the session calls the provider at exactly two points -
get_checkout_total (before confirmation #2) and place_order (after it).

The protocol is deliberately thin: cart/session state lives in the provider,
order truth lives in the DB (PurchaseOrder).
"""

from typing import Protocol

from schemas.offer import Offer


class PurchaseProvider(Protocol):
    name: str
    retailer: str

    async def create_session(self, offer: Offer) -> dict:
        """Open a checkout session at the retailer for one offer."""
        ...

    async def add_to_cart(self, provider_session_id: str, offer: Offer) -> dict:
        ...

    async def get_checkout_total(
        self, provider_session_id: str, offer: Offer
    ) -> dict:
        """Authoritative final total: price + shipping + taxes, as configured."""
        ...

    async def place_order(
        self,
        provider_session_id: str,
        offer: Offer,
        total: float,
        delivery_estimate: str | None = None,
    ) -> dict:
        """Place the order. Returns {order_ref, status, tracking_url}."""
        ...

    async def get_order_status(self, order_ref: str) -> dict:
        """Returns {status, detail, tracking_url} from the retailer."""
        ...


class PurchaseError(Exception):
    """Provider-level failure (network, cancelled, stock change)."""