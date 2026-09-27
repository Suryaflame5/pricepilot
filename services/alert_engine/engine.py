"""Alert engine: periodic scan of active alerts -> notification events."""

import asyncio
import logging

import httpx
from events.bus import AlertTriggeredEvent, EventBus

logger = logging.getLogger(__name__)


class AlertEngine:
    """Polls the API alert-check endpoint; publishes AlertTriggeredEvent."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        poll_seconds: int = 300,
        bus: EventBus | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.poll_seconds = poll_seconds
        self.bus = bus or EventBus()

    async def run_forever(self) -> None:
        logger.info("alert engine started (poll %ss)", self.poll_seconds)
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(f"{self.api_url}/alerts/check", timeout=30)
                    resp.raise_for_status()
                data = resp.json()
                for triggered in data.get("triggered", []):
                    await self.bus.publish(
                        AlertTriggeredEvent(payload={"alert": triggered})
                    )
                    logger.info("alert triggered: %s", triggered)
            except Exception as exc:  # noqa: BLE001 - keep polling alive
                logger.warning("alert check failed: %s", exc)
            await asyncio.sleep(self.poll_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(AlertEngine().run_forever())


if __name__ == "__main__":
    main()
