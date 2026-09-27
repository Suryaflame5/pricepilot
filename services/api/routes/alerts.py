"""Alert routes: CRUD + trigger check (alert_engine polls these)."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from database.models import PriceAlert, PriceObservation
from events.bus import AlertTriggeredEvent
from schemas.alerts import AlertCreate, AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.post("", response_model=AlertOut, status_code=201)
async def create_alert(
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db),
):
    alert = PriceAlert(
        user_id=DEMO_USER_ID,
        product_variant_id=payload.product_variant_id,
        target_price=payload.target_price,
        direction=payload.direction,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("", response_model=list[AlertOut])
async def list_alerts(db: AsyncSession = Depends(get_db)):
    stmt = select(PriceAlert).where(PriceAlert.user_id == DEMO_USER_ID).order_by(PriceAlert.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    alert = await db.get(PriceAlert, alert_id)
    if not alert:
        raise HTTPException(404, "alert not found")
    await db.delete(alert)
    await db.commit()


@router.post("/check")
async def check_alerts(request: Request, db: AsyncSession = Depends(get_db)):
    """Trigger check: called by alert_engine on a schedule."""
    alerts = (
        await db.execute(
            select(PriceAlert).where(PriceAlert.active.is_(True), PriceAlert.triggered_at.is_(None))
        )
    ).scalars().all()
    triggered: list[dict] = []
    for alert in alerts:
        latest = (
            await db.execute(
                select(PriceObservation)
                .join(PriceObservation.listing)
                .where(
                    PriceObservation.listing.has(product_variant_id=alert.product_variant_id),
                )
                .order_by(PriceObservation.observed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is None or latest.effective_price is None:
            continue
        price = float(latest.effective_price)
        hit = price <= alert.target_price if alert.direction == "below" else price == alert.target_price
        if hit:
            alert.triggered_at = datetime.now(timezone.utc)
            triggered.append(
                {
                    "alert_id": str(alert.id),
                    "product_variant_id": str(alert.product_variant_id),
                    "target_price": float(alert.target_price),
                    "current_price": price,
                }
            )
    await db.commit()
    bus = getattr(request.app.state, "event_bus", None)
    if bus:
        for t in triggered:
            await bus.publish(AlertTriggeredEvent(payload={"alert": t, **t}))
    return {"checked": len(alerts), "triggered": triggered}
