"""ShoppingSession state machine (V1.2 P1).

States (spec-locked):
    SEARCHING -> SELECTED -> PRICE_VERIFIED -> CHECKOUT_READY ->
    USER_CONFIRMED -> ORDER_PLACED -> TRACKING -> COMPLETED

Two explicit confirmations:
  #1 confirm the chosen offer     (SELECTED/PRICE_VERIFIED -> CHECKOUT_READY)
  #2 approve the final total      (CHECKOUT_READY -> USER_CONFIRMED -> ORDER_PLACED)

The final effective price is RE-VALIDATED from the database immediately before
place-order; if it drifted from the selected offer the purchase is blocked and
the new total is reported - checkout never uses a stale number.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import PurchaseOrder, ShoppingSession
from price_engine.offers import cheapest_offer, latest_offers, offer_by_listing
from purchase.base import PurchaseError, PurchaseProvider

SESSION_EXPIRY_HOURS = 24

TRANSITIONS: dict[str, set[str]] = {
    "SEARCHING": {"SELECTED"},
    "SELECTED": {"PRICE_VERIFIED"},
    "PRICE_VERIFIED": {"CHECKOUT_READY"},
    "CHECKOUT_READY": {"USER_CONFIRMED"},
    "USER_CONFIRMED": {"ORDER_PLACED"},
    "ORDER_PLACED": {"TRACKING"},
    "TRACKING": {"COMPLETED", "ORDER_PLACED"},
    "COMPLETED": set(),
}


class SessionStateError(Exception):
    """Invalid transition / expired / wrong state for the requested action."""


async def create_session(
    db: AsyncSession,
    *,
    product_variant_id: uuid.UUID,
    strategy: str = "IMMEDIATE",
    conversation_id: str | None = None,
    user_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> ShoppingSession:
    session = ShoppingSession(
        user_id=user_id,
        conversation_id=conversation_id,
        product_variant_id=product_variant_id,
        strategy=strategy,
        status="SEARCHING",
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRY_HOURS),
    )
    db.add(session)
    await db.flush()
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> ShoppingSession:
    session = (
        await db.execute(
            select(ShoppingSession)
            .where(ShoppingSession.id == session_id)
            .options(selectinload(ShoppingSession.selected_listing))
        )
    ).scalar_one_or_none()
    if session is None:
        raise SessionStateError("shopping session not found")
    expire = session.expires_at
    if expire is not None:
        expire = expire.replace(tzinfo=timezone.utc) if expire.tzinfo is None else expire
        if expire < datetime.now(timezone.utc):
            raise SessionStateError("shopping session has expired - start a new one")
    if session.status == "COMPLETED":
        raise SessionStateError("shopping session already completed")
    return session


def _transition(session: ShoppingSession, target: str, action: str) -> None:
    if target not in TRANSITIONS.get(session.status, set()):
        raise SessionStateError(
            f"cannot {action} from state {session.status} (expected state before: "
            f"{', '.join(sorted(s for s, targets in TRANSITIONS.items() if target in targets)) or 'none'})"
        )
    session.status = target


async def session_offers(db: AsyncSession, session: ShoppingSession) -> list[dict]:
    offers = await latest_offers(db, session.product_variant_id)
    return [o.model_dump(mode="json") for o in offers]


async def select_offer(db: AsyncSession, session: ShoppingSession, listing_id: uuid.UUID) -> dict:
    _transition(session, "SELECTED", "select an offer")
    offer = await offer_by_listing(db, listing_id)
    if offer is None or offer.product_variant_id != session.product_variant_id:
        raise SessionStateError("listing is not a trusted offer for this product")
    session.selected_listing_id = listing_id
    session.selected_offer = offer.model_dump(mode="json")
    return offer.model_dump(mode="json")


async def verify_price(db: AsyncSession, session: ShoppingSession) -> dict:
    """Fresh effective price from the DB immediately before checkout steps."""
    _transition(session, "PRICE_VERIFIED", "verify the price")
    current = await offer_by_listing(db, session.selected_listing_id)
    if current is None:
        raise SessionStateError("the selected offer is no longer available")
    selected_price = float((session.selected_offer or {}).get("effective_price") or 0.0)
    changed = abs(current.effective_price - selected_price) > 0.005
    return {
        "status": session.status,
        "price_changed": changed,
        "previous_effective_price": selected_price,
        "current_effective_price": current.effective_price,
    }


async def confirm_offer(
    db: AsyncSession,
    session: ShoppingSession,
    provider: PurchaseProvider,
    accept: bool = True,
) -> dict:
    """Confirmation #1: user approves the selected offer -> prepare checkout."""
    if not accept:
        raise SessionStateError("offer not confirmed; session cancelled by user")
    _transition(session, "CHECKOUT_READY", "confirm the offer")  # requires PRICE_VERIFIED
    offer = await offer_by_listing(db, session.selected_listing_id)
    if offer is None:
        raise SessionStateError("the selected offer is no longer available")
    try:
        provider_session = await provider.create_session(offer)
        await provider.add_to_cart(provider_session["session_id"], offer)
        total = await provider.get_checkout_total(provider_session["session_id"], offer)
    except PurchaseError as exc:
        raise SessionStateError(f"checkout preparation failed at {provider.retailer}: {exc}") from exc
    session.provider_session_id = provider_session.get("session_id")
    session.checkout_total = total.get("total", offer.expected_total)
    session.delivery_estimate = total.get("delivery_estimate")
    session.status = "CHECKOUT_READY"
    return {
        "status": session.status,
        "checkout_total": session.checkout_total,
        "delivery_estimate": session.delivery_estimate,
        "offer": offer.model_dump(mode="json"),
    }


async def place_order(
    db: AsyncSession,
    session: ShoppingSession,
    provider: PurchaseProvider,
    accept: bool = True,
    provider_session_id: str | None = None,
) -> dict:
    """Confirmation #2: user approves the final total -> re-verify -> execute."""
    if not accept:
        raise SessionStateError("purchase not confirmed by user")
    _transition(session, "USER_CONFIRMED", "confirm the purchase")  # requires CHECKOUT_READY

    # THE price re-validation immediately before purchase
    latest = await offer_by_listing(db, session.selected_listing_id)
    if latest is None:
        raise SessionStateError("the selected offer is no longer available before purchase")
    selected_price = float((session.selected_offer or {}).get("effective_price") or 0.0)
    if abs(latest.effective_price - selected_price) > 0.005:
        raise SessionStateError(
            f"price changed since you confirmed: was {selected_price:.2f}, "
            f"now {latest.effective_price:.2f} - reconfirm the new total"
        )

    total = float(session.checkout_total or latest.expected_total)
    session.status = "USER_CONFIRMED"
    try:
        placed = await provider.place_order(
            session.provider_session_id or f"session-{session.id}",
            latest,
            total,
            session.delivery_estimate,
        )
    except PurchaseError as exc:
        raise SessionStateError(f"order placement failed at {provider.retailer}: {exc}") from exc

    order = PurchaseOrder(
        session_id=session.id,
        provider=provider.name,
        retailer_name=latest.retailer_name,
        order_ref=placed.get("order_ref"),
        status=placed.get("status", "TRACKING"),
        total=total,
        tracking_url=placed.get("tracking_url"),
    )
    db.add(order)
    await db.flush()
    session.status = "ORDER_PLACED"
    return {
        "status": session.status,
        "order_ref": order.order_ref,
        "provider": order.provider,
        "retailer_name": order.retailer_name,
        "total": total,
        "tracking_url": order.tracking_url,
    }


async def order_status(
    db: AsyncSession,
    session: ShoppingSession,
    provider: PurchaseProvider,
) -> dict:
    order = (
        await db.execute(
            select(PurchaseOrder).where(PurchaseOrder.session_id == session.id)
        )
    ).scalar_one_or_none()
    if order is None or order.order_ref is None:
        raise SessionStateError("no order has been placed for this session")
    try:
        status = await provider.get_order_status(order.order_ref)
    except PurchaseError as exc:
        raise SessionStateError(str(exc)) from exc
    order.status = status.get("status", order.status)
    order.last_status = status.get("detail")
    if order.status in ("DELIVERED", "COMPLETED"):
        session.status = "COMPLETED"
    elif session.status != "TRACKING":
        session.status = "TRACKING"
    return {
        "status": order.status,
        "order_ref": order.order_ref,
        "provider": order.provider,
        "retailer_name": order.retailer_name,
        "detail": status.get("detail"),
        "tracking_url": status.get("tracking_url") or order.tracking_url,
    }


def resolve_provider(session: ShoppingSession) -> PurchaseProvider:
    from purchase.registry import get_provider

    retailer = (session.selected_offer or {}).get("retailer_name")
    if not retailer:
        raise SessionStateError("no offer selected yet - no provider to talk to")
    return get_provider(retailer)