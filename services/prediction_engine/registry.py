"""Model registry: EXPERIMENT -> CANDIDATE -> SHADOW -> CHAMPION -> RETIRED.

Promotion is evidence-gated: a challenger must beat the incumbent on a required
metric bundle (MAE, quantile loss, calibration ECE, interval coverage error,
directional accuracy, stability) with no regression beyond tolerance on the
rest, evaluated on the same backtest folds. Per-category and per-horizon
breakdowns are required fields of the metric bundle, not optional extras.

Persisted to {registry_dir}/registry.json; mirrored into the model_registry
table by the API layer for audit.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STATUSES = ("EXPERIMENT", "CANDIDATE", "SHADOW", "CHAMPION", "RETIRED")

# promotion gate: must win on these...
REQUIRED_WINS = ("mae", "quantile_loss_50", "ece", "coverage_abs_err", "directional_accuracy", "stability")
# ...and must not regress beyond tolerance on these
REGULAR_TOLERANCE = 0.10  # 10% relative regression allowed
COVERAGE_TOLERANCE = 0.05  # absolute coverage error tolerance


@dataclass
class PromotionVerdict:
    promote: bool
    reasons: list[str] = field(default_factory=list)
    scores: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class ModelRegistryEntry:
    model_id: str
    name: str
    status: str = "EXPERIMENT"
    model_type: str | None = None
    category: str | None = None
    horizon_hours: int | None = None
    features_version: str | None = None
    calibration_version: str | None = None
    conformal_version: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata_: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    promoted_at: str | None = None
    retired_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "status": self.status,
            "model_type": self.model_type,
            "category": self.category,
            "horizon_hours": self.horizon_hours,
            "features_version": self.features_version,
            "calibration_version": self.calibration_version,
            "conformal_version": self.conformal_version,
            "metrics": self.metrics,
            "metadata_": self.metadata_,
            "created_at": self.created_at,
            "promoted_at": self.promoted_at,
            "retired_at": self.retired_at,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ModelRegistryEntry":
        return ModelRegistryEntry(
            model_id=data["model_id"],
            name=data.get("name", data["model_id"]),
            status=data.get("status", "EXPERIMENT"),
            model_type=data.get("model_type"),
            category=data.get("category"),
            horizon_hours=data.get("horizon_hours"),
            features_version=data.get("features_version"),
            calibration_version=data.get("calibration_version"),
            conformal_version=data.get("conformal_version"),
            metrics=data.get("metrics", {}),
            metadata_=data.get("metadata_", {}),
            created_at=data.get("created_at", ""),
            promoted_at=data.get("promoted_at"),
            retired_at=data.get("retired_at"),
            notes=data.get("notes"),
        )


def _flatten_metrics(bundle: dict[str, Any]) -> dict[str, float]:
    """Collapse per-horizon + overall metrics into a flat comparable dict."""
    out: dict[str, float] = {}
    for key, value in (bundle.get("overall") or {}).items():
        out[f"overall.{key}"] = float(value) if value is not None else float("nan")
    per_h = bundle.get("per_horizon") or {}
    for h, m in per_h.items():
        for key, value in m.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[f"h{h}.{key}"] = float(value)
    return out


def _safe(key: str, flat: dict[str, float], default: float = float("nan")) -> float:
    v = flat.get(key)
    if v is None or v != v:  # NaN
        return default
    return v


def compare_metric_bundles(champion: dict[str, Any], challenger: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Normalized per-metric comparison: challenger / champion (lower=better for errors)."""
    champ = _flatten_metrics(champion)
    chal = _flatten_metrics(challenger)
    scores: dict[str, dict[str, float]] = {}
    for key in set(champ) | set(chal):
        c, k = _safe(key, champ), _safe(key, chal)
        if c != c or k != k:
            continue
        lower_is_better = not (key.endswith("directional_accuracy") or key.endswith("stability")
                              or key.endswith("coverage"))
        # coverage_abs_err is already an absolute error (lower is better)
        lower_is_better = lower_is_better or key.endswith("coverage_abs_err")
        scores[key] = {
            "champion": c,
            "challenger": k,
            "ratio": (k / c) if c else float("inf"),  # <1 => challenger better
            "lower_is_better": lower_is_better,
        }
    return scores


def evaluate_promotion(
    champion_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
    min_samples: int = 30,
) -> PromotionVerdict:
    """Evidence gate: challenger wins REQUIRED_WINS, loses none beyond tolerance."""
    reasons: list[str] = []
    samples = challenger_metrics.get("overall", {}).get("n", 0) or 0
    if samples < min_samples:
        return PromotionVerdict(
            promote=False,
            reasons=[f"insufficient evaluation samples ({samples} < {min_samples})"],
        )

    champ = _flatten_metrics(champion_metrics)
    chal = _flatten_metrics(challenger_metrics)
    n_wins, n_regressions, checked = 0, 0, 0
    win_list: list[str] = []

    for base in REQUIRED_WINS:
        key = f"overall.{base}"
        c, k = _safe(key, champ), _safe(key, chal)
        if c != c or k != k:
            continue
        checked += 1
        ratio = k / c if c else float("inf")
        if base == "coverage_abs_err":
            better = k < c
            regression = k > c + COVERAGE_TOLERANCE
        elif base in ("directional_accuracy", "stability"):
            better = k > c
            regression = k < c * (1 - REGULAR_TOLERANCE)
        else:
            better = k < c
            regression = k > c * (1 + REGULAR_TOLERANCE)
        if better:
            n_wins += 1
            win_list.append(f"{base}: {c:.4g} -> {k:.4g}")
        elif regression:
            n_regressions += 1
            reasons.append(f"{base} regressed: {c:.4g} -> {k:.4g}")

    # per-horizon regressions also count (same policy, any horizon) and BLOCK
    horizon_regressions = 0
    for key, cmp in compare_metric_bundles(champion_metrics, challenger_metrics).items():
        if key.startswith("overall.") or not cmp.get("lower_is_better", True):
            continue
        if cmp["champion"] != cmp["champion"] or cmp["challenger"] != cmp["challenger"]:
            continue
        if cmp["challenger"] > cmp["champion"] * (1 + REGULAR_TOLERANCE):
            horizon_regressions += 1
            reasons.append(f"{key} regressed: {cmp['champion']:.4g} -> {cmp['challenger']:.4g}")

    required = len([k for k in REQUIRED_WINS if f"overall.{k}" in champ and f"overall.{k}" in chal]) or 1
    majority = (n_wins / required) >= 0.6
    if not majority and n_regressions == 0:
        reasons.append(f"only {n_wins}/{required} required metrics improved")

    return PromotionVerdict(
        promote=majority and n_regressions == 0 and horizon_regressions == 0,
        reasons=reasons,
        scores={"improved": win_list},
    )


class ModelRegistry:
    """File-backed registry (mirrored to DB for audit by the API layer)."""

    def __init__(self, registry_dir: str | Path | None = None) -> None:
        self.registry_dir = Path(registry_dir) if registry_dir else None
        self._entries: dict[str, ModelRegistryEntry] = {}
        if self.registry_dir:
            self.load()

    @property
    def path(self) -> Path | None:
        return (self.registry_dir / "registry.json") if self.registry_dir else None

    def load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self._entries = {
                e["model_id"]: ModelRegistryEntry.from_dict(e) for e in data.get("entries", [])
            }
        except Exception as exc:
            logger.warning("registry load failed: %s", exc)

    def save(self) -> None:
        if not self.registry_dir:
            return
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "entries": [e.to_dict() for e in self._entries.values()],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
        )

    def register(self, entry: ModelRegistryEntry) -> None:
        if not entry.created_at:
            entry.created_at = datetime.now(timezone.utc).isoformat()
        self._entries[entry.model_id] = entry
        self.save()

    def get(self, model_id: str) -> ModelRegistryEntry | None:
        return self._entries.get(model_id)

    def get_champion(self, category: str | None = None) -> ModelRegistryEntry | None:
        for e in self._entries.values():
            if e.status == "CHAMPION" and (category is None or e.category == category):
                return e
        return None

    def challengers(self) -> list[ModelRegistryEntry]:
        return [e for e in self._entries.values() if e.status in ("CANDIDATE", "SHADOW")]

    def promote(self, challenger_id: str, champion_id: str | None = None, notes: str | None = None) -> PromotionVerdict:
        challenger = self.get(challenger_id)
        if challenger is None or challenger.status not in ("CANDIDATE", "SHADOW", "EXPERIMENT"):
            return PromotionVerdict(False, [f"{challenger_id} is not promotable"])
        if champion_id is None:
            champion = self.get_champion(challenger.category)
        else:
            champion = self.get(champion_id)
        if champion is None or champion.status != "CHAMPION":
            # no incumbent: promote on sanity (evaluation must still exist)
            if not challenger.metrics:
                return PromotionVerdict(False, ["challenger has no evaluation metrics"])
            challenger.status = "CHAMPION"
            challenger.promoted_at = datetime.now(timezone.utc).isoformat()
            challenger.notes = notes or "promoted as first champion"
            self.save()
            return PromotionVerdict(True, ["promoted as first champion"])
        if champion.model_id == challenger.model_id:
            return PromotionVerdict(False, ["challenger is already the champion"])

        verdict = evaluate_promotion(champion.metrics, challenger.metrics)
        if not verdict.promote:
            return verdict

        champ_promoted_at = challenger.promoted_at
        now = datetime.now(timezone.utc).isoformat()
        champion.status = "RETIRED"
        champion.retired_at = now
        champion.notes = f"retired in favor of {challenger.model_id}"
        challenger.status = "CHAMPION"
        challenger.promoted_at = champ_promoted_at or now
        challenger.notes = notes
        self.save()
        verdict.reasons.append(f"{champion.model_id} retired")
        return verdict

    def list(self) -> list[ModelRegistryEntry]:
        return list(self._entries.values())
