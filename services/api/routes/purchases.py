"""Purchase workflow routes (V1.2 P1).

Explicit-confirmation flow:
    SEARCH -> RECOMMEND -> USER CONFIRMS OFFER -> PREPARE CHECKOUT ->
    SHOW FINAL TOTAL -> USER CONFIRMS PURCHASE -> EXECUTE

Confirmation #1: POST /{id}/confirm        (offer selection approved)
Confirmation #2: POST /{id}/place-order    (final total + delivery approved)

The final price is re-validated from the DB inside place-order; a price drift
blocks execution and reports the new total instead of silently proceeding.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from database.models import ShoppingSession
from purchase.base import PurchaseError
from purchase.registry import registered_providers
from purchase import session as sess
from purchase.session import SessionStateError, resolve_provider
from schemas.purchase import (
    CheckoutReadyOut,
    ConfirmIn,
    OrderPlacedOut,
    OrderStatusOut,
    PriceVerificationOut,
    SelectListingIn,
    SessionOut,
    SessionWithOffersOut,
    ShoppingSessionCreate,
)

router = APIRouter(prefix="/shopping-sessions", tags=["shopping-sessions"])


async def _session(db: AsyncSession, session_id: uuid.UUID) -> ShoppingSession:
    try:
        return await sess.get_session(db, session_id)
    except SessionStateError as exc:
        raise HTTPException(404, str(exc)) from exc


def _session_out(s: ShoppingSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        product_variant_id=s.product_variant_id,
        conversation_id=s.conversation_id,
        strategy=s.strategy,
        status=s.status,
        selected_listing_id=s.selected_listing_id,
        selected_offer=s.selected_offer or {},
        checkout_total=float(s.checkout_total) if s.checkout_total is not None else None,
        delivery_estimate=s.delivery_estimate,
        created_at=s.created_at,
        expires_at=s.expires_at,
    )


@router.post("", response_model=SessionWithOffersOut, status_code=201)
async def create_shopping_session(
    payload: ShoppingSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    s = await sess.create_session(
        db,
        product_variant_id=payload.product_variant_id,
        strategy=payload.strategy,
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
    )
    offers = await sess.session_offers(db, s)
    await db.commit()
    return SessionWithOffersOut(**_session_out(s).model_dump(), offers=offers)


@router.get("/providers/list", response_model=list[str])
async def list_providers():
    return registered_providers()


@router.get("/{session_id}", response_model=SessionOut)
async def get_shopping_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    s = await _session(db, session_id)
    return _session_out(s)


@router.post("/{session_id}/select", response_model=SessionOut)
async def select_offer(
    session_id: uuid.UUID,
    payload: SelectListingIn,
    db: AsyncSession = Depends(get_db),
):
    s = await _session(db, session_id)
    try:
        await sess.select_offer(db, s, payload.listing_id)
    except (SessionStateError, PurchaseError) as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return _session_out(s)


@router.post("/{session_id}/verify-price", response_model=PriceVerificationOut)
async def verify_price(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    s = await _session(db, session_id)
    try:
        result = await sess.verify_price(db, s)
    except SessionStateError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return PriceVerificationOut(**result)


@router.post("/{session_id}/confirm", response_model=CheckoutReadyOut)
async def confirm_offer(
    session_id: uuid.UUID,
    payload: ConfirmIn,
    db: AsyncSession = Depends(get_db),
):
    """Confirmation #1 - the user approves the selected offer."""
    s = await _session(db, session_id)
    try:
        result = await sess.confirm_offer(db, s, resolve_provider(s), accept=payload.accept)
    except (SessionStateError, PurchaseError) as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return CheckoutReadyOut(**result)


@router.post("/{session_id}/place-order", response_model=OrderPlacedOut)
async def place_order(
    session_id: uuid.UUID,
    payload: ConfirmIn,
    db: AsyncSession = Depends(get_db),
):
    """Confirmation #2 - final total + delivery approved; executes the order.

    Price is re-validated immediately before placement; a drift aborts with 409
    and the user must re-confirm the new total.
    """
    s = await _session(db, session_id)
    try:
        result = await sess.place_order(db, s, resolve_provider(s), accept=payload.accept)
    except (SessionStateError, PurchaseError) as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return OrderPlacedOut(**result)


@router.get("/{session_id}/order", response_model=OrderStatusOut)
async def order_status(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    s = await _session(db, session_id)
    try:
        result = await sess.order_status(db, s, resolve_provider(s))
    except (SessionStateError, PurchaseError) as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return OrderStatusOut(**result)