"""WebSocket live-event endpoint: /ws/live (V2 realtime data layer)."""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api.realtime import get_hub

router = APIRouter()


@router.websocket("/ws/live")
async def ws_live(
    websocket: WebSocket,
    topics: str = Query(""),
    entities: str = Query(""),
):
    """Subscribe to typed live events. Snapshot comes from REST; this socket
    only pushes incremental updates.

    Query filters:
      topics:   comma-separated event types (default: market + intelligence)
      entities: comma-separated aggregate ids (listing/variant ids)
    """
    topic_set = {t.strip() for t in topics.split(",") if t.strip()} or {
        "price.collected",
        "price.changed",
        "price.dropped",
        "price.spike",
        "stock.changed",
        "seller.changed",
        "promotion.started",
        "promotion.ended",
        "prediction.updated",
        "alert.triggered",
        "decision.changed",
    }
    entity_set = {e.strip() for e in entities.split(",") if e.strip()}
    hub = get_hub()
    try:
        await hub.handle(websocket, topic_set, entity_set)
    except WebSocketDisconnect:
        pass