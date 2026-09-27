"""Seed the database with synthetic catalog + price history (dev/demo/CI)."""

import asyncio
import os

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Event,
    Listing,
    PriceAlert,
    PriceObservation,
    Product,
    ProductVariant,
    Retailer,
    User,
    WatchlistItem,
)
from database.session import create_engine, create_session_factory, init_db
from ml.datasets.synthetic import make_records

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pricepilot:pricepilot@localhost:5432/pricepilot",
)


async def seed(db: AsyncSession, products: int = 5, days: int = 365, obs_per_day: int = 4) -> None:
    for table in (PriceObservation, Listing, ProductVariant, Product, Retailer, Event, PriceAlert, WatchlistItem):
        await db.execute(delete(table))
    await db.commit()

    records = make_records(products=products, days=days, obs_per_day=obs_per_day, seed=7)

    for r in records["retailers"]:
        db.add(Retailer(**r))
    for p in records["products"]:
        db.add(Product(**p))
    for v in records["variants"]:
        db.add(ProductVariant(**v))
    for l in records["listings"]:
        db.add(Listing(**l))
    for e in records["events"]:
        db.add(Event(**e))
    await db.commit()

    # bulk-insert observations (the big table)
    obs_rows = records["observations"]
    await db.execute(PriceObservation.__table__.insert(), obs_rows)
    await db.commit()

    db.add(
        User(
            id=__import__("uuid").UUID("00000000-0000-0000-0000-000000000001"),
            email="demo@pricepilot.ai",
            name="Demo User",
        )
    )
    await db.commit()
    print(
        f"seeded: {len(records['retailers'])} retailers, {len(records['products'])} products, "
        f"{len(records['listings'])} listings, {len(obs_rows)} price observations, {len(records['events'])} events"
    )


async def main() -> None:
    engine = create_engine(DATABASE_URL)
    await init_db(engine)
    factory = create_session_factory(engine)
    async with factory() as db:
        await seed(
            db,
            products=int(os.getenv("SEED_PRODUCTS", "5")),
            days=int(os.getenv("SEED_HISTORY_DAYS", "365")),
            obs_per_day=int(os.getenv("SEED_OBSERVATIONS_PER_DAY", "4")),
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
