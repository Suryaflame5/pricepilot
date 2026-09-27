"""Adaptive polling CLI (V1.2 P0 - continuous price intelligence).

Computes a per-listing poll interval from measured volatility, active alerts
and price-change rate, collects due listings through the registered collector
and pushes results through the IngestionPipeline (quarantine -> match ->
quality -> TRUSTED observations).

Run: python -m ml.intake.run_scheduler [--once] [--dry-run] [--limit N]
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from database.session import create_engine, create_session_factory, init_db
from price_engine.collectors.mock import MockCollector
from price_engine.collectors.registry import create_collector
from price_engine.collectors.scheduler import AdaptiveScheduler
from price_engine.pipeline import IngestionPipeline

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pricepilot:pricepilot@localhost:5432/pricepilot",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_scheduler")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run a single collection round and exit")
    parser.add_argument("--dry-run", action="store_true", help="compute intervals only; collect nothing")
    parser.add_argument("--limit", type=int, default=None, help="at most N due targets per round")
    parser.add_argument("--retailer", default="mock", help="collector name; mock is the default")
    parser.add_argument("--poll-seconds", type=int, default=60, help="loop delay for continuous mode")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    await init_db(engine)
    factory = create_session_factory(engine)

    try:
        collector = create_collector(args.retailer)
    except KeyError:
        logger.warning("collector '%s' not registered; falling back to mock", args.retailer)
        collector = MockCollector()

    scheduler = AdaptiveScheduler(factory)
    pipeline = IngestionPipeline(factory)

    async def sink(results) -> None:
        reports = await pipeline.ingest_results(results)
        ok = sum(1 for r in reports if r.get("status") == "VERIFIED")
        logger.info("ingested %d/%d observations", ok, len(reports))

    if args.once or args.dry_run:
        async with factory() as db:
            report = await scheduler.run_round(
                db, collector, on_results=sink, dry_run=args.dry_run,
                now=datetime.now(timezone.utc),
            )
        print("round report:", report)
        return

    logger.info("continuous mode: polling every %ds (intervals are per-listing)", args.poll_seconds)
    await scheduler.run_forever(collector, on_results=sink, poll_ms=args.poll_seconds * 1000)


if __name__ == "__main__":
    asyncio.run(main())