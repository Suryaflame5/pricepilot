"""Model registry: weights + metadata persistence (blueprint: model_registry)."""

import json
from datetime import datetime, timezone
from pathlib import Path


class ModelRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_weights(self, weights: dict, version: str) -> Path:
        path = self.root / "ensemble_weights.json"
        path.write_text(
            json.dumps(
                {
                    "weights": weights,
                    "version": version,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
        )
        return path

    def load_weights(self) -> dict | None:
        path = self.root / "ensemble_weights.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def log_run(self, name: str, metrics: dict) -> Path:
        path = self.root / "runs.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "name": name,
                        "metrics": metrics,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                )
                + "\n"
            )
        return path
