"""Shared HTTP client with retries/backoff and polite defaults.

Retailer adapters MUST respect terms of service and access controls; this client
exists to make permitted collection robust, not to evade blocks.
"""

from typing import Any

import httpx

from price_engine.collectors.base import CollectorError, DegradedError

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.8",
    "User-Agent": (
        "PricePilot/0.9 (+https://github.com/pricepilot; collection-bot; "
        "contact: ops@pricepilot.example)"
    ),
}

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(self, timeout_s: float = 15.0, max_retries: int = 2) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_s),
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )
        self._max_retries = max_retries

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.get(url, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = CollectorError(f"transport failure for {url}: {exc}")
                continue
            if resp.status_code in RETRY_STATUS and attempt < self._max_retries:
                last_exc = CollectorError(f"http {resp.status_code} for {url}")
                continue
            if resp.status_code in (403, 404):
                raise DegradedError(f"http {resp.status_code} for {url} (blocked/gone)")
            resp.raise_for_status()
            return resp
        raise CollectorError(f"gave up after {self._max_retries + 1} attempts: {last_exc}")

    async def close(self) -> None:
        await self._client.aclose()


async def fetch_json(url: str, client: HttpClient | None = None) -> dict[str, Any]:
    own = client is None
    client = client or HttpClient()
    try:
        resp = await client.get(url)
        return resp.json()
    finally:
        if own:
            await client.close()
