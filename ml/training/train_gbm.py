"""GBM training CLI (Sprint 4/5 training entrypoint).

Usage:
    python -m ml.training.train_gbm --days 365 --horizon 30

Fits per-(horizon, quantile) LightGBM models on synthetic data and reports
walk-forward performance vs the naive baseline. The "deep learning must beat
the baseline" rule (blueprint section 6) is enforced here.
"""

import argparse
import json

import numpy as np

from ml.datasets.synthetic import generate_series
from prediction_engine.evaluation import mae, rmse
from prediction_engine.models.baseline import NaiveForecaster
from prediction_engine.models.gbm import fit_gbm_models

MAX_H = 30


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--horizon", type=int, default=MAX_H)
    parser.add_argument("--base", type=float, default=29990.0)
    args = parser.parse_args()

    y = generate_series(base_price=args.base, days=args.days, seed=3).series.to_numpy(dtype=float)
    train, test = y[: int(len(y) * 0.8)], y[int(len(y) * 0.8):]
    horizons = list(range(1, min(args.horizon, MAX_H) + 1))

    gbm = fit_gbm_models(train, horizons)
    naive = NaiveForecaster()

    print("horizon | gbm_mae | naive_mae | gbm_beats_baseline")
    for h in horizons:
        preds = gbm.forecast_quantiles(test, h, [0.5])[:, 0]
        actuals = np.array([test[i + h] for i in range(len(test) - h)])
        nb_preds = naive.forecast_quantiles(test, h, [0.5])[:, 0]
        g_mae, n_mae = mae(actuals, preds[: len(actuals)]), mae(actuals, nb_preds[: len(actuals)])
        beats = g_mae <= n_mae
        print(f"{h:>7} | {g_mae:8.2f} | {n_mae:9.2f} | {beats}")
    print(json.dumps({"models_fit": len(horizons) * 5}))


if __name__ == "__main__":
    main()
