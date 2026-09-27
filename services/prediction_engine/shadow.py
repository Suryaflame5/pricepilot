"""Shadow inference: challengers run alongside the champion but never serve users.

Every shadow forecast is logged (JSONL) with the challenger id, model version,
inputs fingerprint and quantile path, so promotion decisions use live behavior
in addition to backtests. Serving code (API) only ever consumes the champion.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ShadowRunner:
    """Logs challenger predictions. The champion path stays untouched: shadow
    output is never returned to callers."""

    def __init__(self, log_dir: str | Path, enabled: bool = True) -> None:
        self.log_dir = Path(log_dir)
        self.enabled = enabled
        if enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        challenger_id: str,
        *,
        series_fingerprint: str,
        horizon: int,
        quantiles: list[float],
        per_model: dict[str, float],
        champion_id: str | None = None,
        champion_quantiles: list[float] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"shadow": False, "challenger_id": challenger_id}
        record = {
            "shadow_id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "challenger_id": challenger_id,
            "champion_id": champion_id,
            "series_fingerprint": series_fingerprint,
            "horizon": int(horizon),
            "quantiles": [round(float(q), 4) for q in quantiles],
            "per_model": per_model,
            "champion_quantiles": [round(float(q), 4) for q in champion_quantiles] if champion_quantiles else None,
            "context": context or {},
        }
        try:
            with (self.log_dir / f"{challenger_id}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError as exc:
            logger.warning("shadow log write failed: %s", exc)
        return record

    def recent(self, challenger_id: str, limit: int = 50) -> list[dict[str, Any]]:
        path = self.log_dir / f"{challenger_id}.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh.readlines()[-limit:]:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            return []
        return rows

    def live_coverage_hint(self, challenger_id: str, limit: int = 200) -> dict[str, Any]:
        """Rough live coverage check on p50 errors (shadow only, informational)."""
        rows = self.recent(challenger_id, limit)
        errors = [abs(r["quantiles"][3] - r["quantiles"][3]) for r in rows]  # placeholder
        return {"records": len(rows), "note": "resolve actuals against shadow log for real coverage"}
