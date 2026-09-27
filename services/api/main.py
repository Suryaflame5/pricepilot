"""PricePilot API - FastAPI entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.dependencies import engine, session_factory
from api.realtime import RealtimeHub, configure_hub
from api.routes import (
    admin,
    alerts,
    chat,
    matching,
    monitoring,
    predictions,
    prices,
    products,
    purchases,
    realtime,
    watchlist,
)
from api.routes import data_import
from database.session import init_db
from events.bus import EventBus
from price_engine.pipeline import IngestionPipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(engine)
    app.state.event_bus = EventBus(settings.redis_url)
    app.state.ingestion_pipeline = IngestionPipeline(session_factory, app.state.event_bus)
    hub = RealtimeHub(app.state.event_bus)
    app.state.realtime_hub = hub
    configure_hub(hub)
    await hub.start_heartbeat()
    yield
    if hub._heartbeat_task is not None:
        hub._heartbeat_task.cancel()
        if app.state.event_bus._redis:
            await app.state.event_bus._redis.close()


app = FastAPI(
    title="PricePilot API",
    version="0.1.0",
    description="Rigorous price forecasting and shopping-decision engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    products.router,
    prices.router,
    predictions.router,
    alerts.router,
    chat.router,
    watchlist.router,
    matching.router,
    monitoring.router,
    purchases.router,
    admin.router,
    data_import.router,
):
    app.include_router(router)

app.include_router(realtime.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "pricepilot-api", "version": "0.1.0"}
