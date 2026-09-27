"""Backtest CLI: walk-forward evaluation of the full model zoo on a series.

Usage:
    python -m ml.experiments.run_backtest [--days 365] [--horizon 30] [--base 29990] [--learn-weights]

Learns ensemble weights from validation performance and persists them to the
model registry (ml/model_registry/ensemble_weights.json).
"""

import argparse
import json
from pathlib import Path

import numpy as np

from prediction_engine.backtesting import walk_forward_backtest
from prediction_engine.models.base import QUANTILES
from prediction_engine.models.baseline import (
    ExponentialSmoothingForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
)
from prediction_engine.models.gbm import fit_gbm_models
from prediction_engine.models.statistical import ARIMAForecaster
from ml.datasets.synthetic import generate_series

DEFAULT_REGISTRY = Path("ml/model_registry")


def build_zoo(y: np.ndarray, horizon: int) -> list:
    models = [
        NaiveForecaster(),
        MovingAverageForecaster(window=7),
        ExponentialSmoothingForecaster(alpha=0.3),
        SeasonalNaiveForecaster(period=7),
        ARIMAForecaster(),
    ]
    if len(y) >= 100:
        models.append(fit_gbm_models(y, list(range(1, min(horizon, 30) + 1))))
    return models


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--base", type=float, default=29990.0)
    parser.add_argument("--learn-weights", action="store_true")
    args = parser.parse_args()

    synthetic = generate_series(base_price=args.base, days=args.days, seed=11)
    y = synthetic.series.to_numpy(dtype=float)
    models = build_zoo(y, args.horizon)

    result = walk_forward_backtest(y, args.horizon, models, n_folds=10)
    print("=== Backtest (walk-forward, ensemble) ===")
    print(json.dumps(result.metrics, indent=2))
    print(f"folds={result.folds} samples={result.samples}")
    print(f"90% conformal coverage per horizon: {result.coverage_90}")
    print(f"calibration pairs: {len(result.prob_outcome)}")

    if args.learn_weights:
        from prediction_engine.ensemble import Ensemble

        ensemble = Ensemble(models)
        ensemble.fit_weights(y, args.horizon, QUANTILES)
        print("=== Learned ensemble weights ===")
        print(json.dumps(ensemble.weights, indent=2))
        DEFAULT_REGISTRY.mkdir(parents=True, exist_ok=True)
        (DEFAULT_REGISTRY / "ensemble_weights.json").write_text(
            json.dumps({"weights": ensemble.weights, "version": "pricepilot-v1.0.0"}, indent=2)
        )
        print(f"saved -> {DEFAULT_REGISTRY / 'ensemble_weights.json'}")


if __name__ == "__main__":
    main()
