"""V1.1 reliability tests: product matching policy, model registry promotion,
shadow inference, drift detection, hierarchical calibration, regime conformal,
retailer reconciliation, three-part confidence."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import numpy as np
import pandas as pd
import pytest

from prediction_engine.calibration import CalibrationStore, MIN_CALIBRATION_PAIRS
from prediction_engine.conformal import RegimeConformalStore, conformal_quantile, interval
from prediction_engine.drift import detect_feature_drift, evaluate_coverage, ks_test, psi
from prediction_engine.inference import PredictionEngine, ForecastResult
from prediction_engine.reconciliation import forecast_retailer, reconcile
from prediction_engine.registry import (
    ModelRegistry,
    ModelRegistryEntry,
    evaluate_promotion,
)
from prediction_engine.shadow import ShadowRunner
from product_engine.matching import (
    AUTO_MATCH_THRESHOLD,
    REVIEW_MATCH_THRESHOLD,
    TextEmbedder,
    decide,
    find_best_match,
    jaccard,
    match_score,
    tokenize,
)


# ------------------------------------------------------------ matching
class TestMatchingPolicy:
    def test_identifier_equality_is_auto_match(self):
        query = {"brand": "Sony", "model": "WH-1000XM5", "gtin": "4548736117576", "title": "sony x"}
        cand = {"brand": "Sony", "model": "WH-1000XM5", "gtin": "4548736117576", "title": "sony headphones"}
        assert match_score(query, cand) == 1.0
        assert decide(1.0) == "AUTO_MATCH"

    def test_truncated_gtin_gets_high_but_not_auto_score(self):
        query = {"gtin": "4548736117576", "title": "x"}
        cand = {"gtin": "8736117576", "title": "y"}  # last 8 digits agree
        assert match_score(query, cand) == 0.99
        assert decide(0.99) == "REVIEW"

    def test_threshold_band_policy(self):
        assert decide(AUTO_MATCH_THRESHOLD) == "AUTO_MATCH"
        assert decide((AUTO_MATCH_THRESHOLD + REVIEW_MATCH_THRESHOLD) / 2) == "REVIEW"
        assert decide(REVIEW_MATCH_THRESHOLD - 0.01) == "NO_MATCH"

    def test_jaccard_and_tokenize(self):
        a = tokenize("Sony WH-1000XM5 Headphones")
        b = tokenize("Sony WH-1000XM5 Headphones Black")
        assert jaccard(a, b) > 0.7
        assert tokenize("₹27,022") == {"27022"}

    def test_embedder_similarity(self):
        emb = TextEmbedder()
        s = emb.similarity("Sony WH-1000XM5 Wireless Headphones", "Sony WH-1000XM5 Wireless Headphones")
        assert s > 0.99
        low = emb.similarity("Sony Headphones", "Samsung TV")
        assert low < 0.4

    def test_find_best_match_picks_correct_candidate(self):
        candidates = [
            (1, {"title": "Apple AirPods Pro 2", "brand": "Apple"}),
            (2, {"title": "Sony WH-1000XM5", "brand": "Sony", "gtin": "4548736117576"}),
            (3, {"title": "Boat Bassheads 900", "brand": "boAt"}),
        ]
        best, score, decision, details = find_best_match(
            {"title": "Sony WH-1000XM5 Headphones", "brand": "Sony", "gtin": "4548736117576"},
            candidates,
            TextEmbedder(),
        )
        assert best == 2 and decision == "AUTO_MATCH"


# ------------------------------------------------------------ registry / promotion
class TestRegistry:
    def _bundle(self, mae, ql, ece, cov_err, da, stab, n=500):
        return {
            "overall": {
                "mae": mae, "quantile_loss_50": ql, "ece": ece,
                "coverage_abs_err": cov_err, "directional_accuracy": da,
                "stability": stab, "n": n,
            },
            "per_horizon": {
                "1": {"mae": mae * 1.1, "quantile_loss_50": ql * 1.1, "n": 100},
            },
        }

    def test_better_challenger_promotes(self, tmp_path):
        reg = ModelRegistry(tmp_path / "reg")
        reg.register(ModelRegistryEntry(model_id="c1", name="champ", status="CHAMPION",
                                        metrics=self._bundle(100, 50, 0.04, 0.03, 0.55, 0.6)))
        reg.register(ModelRegistryEntry(model_id="c2", name="chal", status="CANDIDATE",
                                        metrics=self._bundle(80, 40, 0.03, 0.02, 0.58, 0.65)))
        verdict = reg.promote("c2", champion_id="c1")
        assert verdict.promote
        assert reg.get("c1").status == "RETIRED"
        assert reg.get("c2").status == "CHAMPION"

    def test_worse_challenger_not_promoted(self, tmp_path):
        reg = ModelRegistry(tmp_path / "reg")
        reg.register(ModelRegistryEntry(model_id="c1", name="champ", status="CHAMPION",
                                        metrics=self._bundle(80, 40, 0.03, 0.02, 0.58, 0.65)))
        reg.register(ModelRegistryEntry(model_id="c2", name="chal", status="CANDIDATE",
                                        metrics=self._bundle(120, 70, 0.08, 0.06, 0.5, 0.4)))
        verdict = reg.promote("c2", champion_id="c1")
        assert not verdict.promote
        assert reg.get("c1").status == "CHAMPION"

    def test_insufficient_samples_blocks_promotion(self):
        champ = self._bundle(100, 50, 0.04, 0.03, 0.55, 0.6, n=500)
        chal = self._bundle(50, 25, 0.02, 0.01, 0.6, 0.7, n=10)
        assert not evaluate_promotion(champ, chal).promote

    def test_per_horizon_regression_blocks_promotion(self):
        champ = self._bundle(100, 50, 0.04, 0.03, 0.55, 0.6)
        champ["per_horizon"]["5"] = {"mae": 120.0, "quantile_loss_50": 60.0, "n": 50}
        chal = self._bundle(80, 40, 0.03, 0.02, 0.58, 0.65)
        chal["per_horizon"]["5"] = {"mae": 500.0, "quantile_loss_50": 300.0, "n": 50}
        verdict = evaluate_promotion(champ, chal)
        assert not verdict.promote
        assert any("regressed" in r for r in verdict.reasons)

    def test_registry_round_trip(self, tmp_path):
        reg = ModelRegistry(tmp_path / "reg")
        reg.register(ModelRegistryEntry(model_id="m1", name="x", status="CHAMPION", metrics={"overall": {"mae": 1}}))
        reg2 = ModelRegistry(tmp_path / "reg")
        assert reg2.get("m1").status == "CHAMPION"


# ------------------------------------------------------------ shadow
class TestShadow:
    def test_shadow_logs_without_serving(self, tmp_path):
        runner = ShadowRunner(tmp_path / "shadow")
        record = runner.log("challenger-gbm-v1", series_fingerprint="abc", horizon=30,
                            quantiles=[100, 110, 120, 130, 140, 150, 160],
                            per_model={"gbm": 130.0}, champion_id="champion-v1")
        assert record["challenger_id"] == "challenger-gbm-v1"
        rows = runner.recent("challenger-gbm-v1")
        assert len(rows) == 1 and rows[0]["horizon"] == 30

    def test_disabled_shadow_no_writes(self, tmp_path):
        runner = ShadowRunner(tmp_path / "shadow2", enabled=False)
        runner.log("x", series_fingerprint="f", horizon=1, quantiles=[1], per_model={})
        assert not (tmp_path / "shadow2" / "x.jsonl").exists()


# ------------------------------------------------------------ drift
class TestDrift:
    def test_ks_identical_distributions(self):
        rng = np.random.default_rng(0)
        a = rng.normal(0, 1, 500)
        d, p = ks_test(a, rng.normal(0, 1, 500))
        assert p > 0.05

    def test_ks_detects_shift(self):
        rng = np.random.default_rng(1)
        d, p = ks_test(rng.normal(0, 1, 500), rng.normal(3, 1, 500))
        assert p < 0.01

    def test_feature_drift_detects_regime_change(self):
        rng = np.random.default_rng(2)
        baseline = 1000 + np.cumsum(rng.normal(0, 3, 120))
        promo = baseline[-1] * np.linspace(1.0, 0.85, 10)
        report = detect_feature_drift(baseline, promo)
        assert report.drifted
        assert report.details["ks_p"] < 0.05

    def test_no_drift_same_regime(self):
        rng = np.random.default_rng(3)
        base = 1000 + np.cumsum(rng.normal(0, 3, 120))
        recent = base[-20:] + rng.normal(0, 1, 20)
        assert not detect_feature_drift(base, recent).drifted

    def test_coverage_monitor(self):
        out = evaluate_coverage([True, True, True, False, True, True, True, True, True, True])
        assert abs(out["coverage"] - 0.9) < 1e-9
        assert out["within_tolerance"]
        bad = evaluate_coverage([True] * 5, level=0.9)
        assert bad["drifted"]

    def test_psi(self):
        rng = np.random.default_rng(4)
        p = psi(rng.normal(0, 1, 1000), rng.normal(0, 1, 1000))
        assert p < 0.5
        big = psi(rng.normal(0, 1, 1000), rng.normal(5, 1, 1000))
        assert big > 0.5


# ------------------------------------------------------------ calibration hierarchy
class TestCalibration:
    def test_min_pairs_guard(self, tmp_path):
        store = CalibrationStore(tmp_path / "cal")
        rng = np.random.default_rng(5)
        pr = rng.uniform(0, 1, MIN_CALIBRATION_PAIRS - 10)
        assert not store.save_fit(pr, (pr > 0.5).astype(int), "headphones:30")

    def test_fits_with_enough_pairs(self, tmp_path):
        store = CalibrationStore(tmp_path / "cal")
        rng = np.random.default_rng(6)
        pr = rng.uniform(0, 1, 200)
        assert store.save_fit(pr, (pr > 0.5).astype(int), "headphones:30")

    def test_hierarchical_backoff(self, tmp_path):
        store = CalibrationStore(tmp_path / "cal2")
        rng = np.random.default_rng(7)
        pr = rng.uniform(0, 1, 200)
        # keys are in HOURS (engine unit): 24*30h == 30d
        store.save_fit(pr, (pr > 0.5).astype(int), "headphones:720")
        # specific (category:horizon:regime:retailer) misses -> falls to (category:horizon)
        out = store.apply(np.array([0.9]), "headphones", 24 * 30, regime="PROMOTION", retailer="croma")
        assert store.last_used_key == "headphones:720"
        assert 0.0 <= float(out[0]) <= 1.0

    def test_global_fallback_when_nothing_fits(self, tmp_path):
        store = CalibrationStore(tmp_path / "cal3")
        out = store.apply(np.array([0.7]), "mystery", 24 * 30, regime="NORMAL")
        assert out[0] == 0.7  # uncalibrated -> raw, honest
        assert store.last_used_key is None


# ------------------------------------------------------------ regime conformal
class TestConformal:
    def test_qhat_calculation(self):
        residuals = np.abs(np.random.default_rng(8).normal(0, 50, 100))
        q = conformal_quantile(residuals, 0.9)
        assert q > 0
        lo, hi = interval(1000.0, q)
        assert lo < 1000.0 < hi

    def test_promotion_bucket_wider_than_global(self, tmp_path):
        store = RegimeConformalStore(tmp_path / "conf")
        rng = np.random.default_rng(9)
        store.fit_bucket(1, "PROMOTION", np.abs(rng.normal(300, 80, 60)), 0.9)
        store.fit_bucket(1, "GLOBAL", np.abs(rng.normal(300, 100, 60)), 0.9)
        store.save()
        store2 = RegimeConformalStore(tmp_path / "conf")
        store2.load()
        q_promo, used_promo = store2.qhat_for(1, "PROMOTION", 0.9)
        q_normal, used_normal = store2.qhat_for(1, "NORMAL", 0.9)
        assert used_promo == "PROMOTION" and used_normal == "GLOBAL"
        assert q_promo < q_normal  # PROMOTION bucket is tighter => global fallback wider

    def test_fallback_to_heuristic(self, tmp_path):
        store = RegimeConformalStore(tmp_path / "conf2")
        q, used = store.qhat_for(1, "NORMAL", 0.9, fallback_qhat=42.0)
        assert used == "heuristic" and q == 42.0


# ------------------------------------------------------------ reconciliation
class TestReconciliation:
    def test_offsets_recovered(self):
        rng = np.random.default_rng(10)
        t = pd.date_range("2025-01-01", periods=120, freq="D")
        market = 1000 + np.cumsum(rng.normal(0, 4, 120))
        rec = reconcile({
            "croma": pd.Series(market + 40 + rng.normal(0, 3, 120), index=t),
            "flipkart": pd.Series(market - 25 + rng.normal(0, 3, 120), index=t),
            "reliance": pd.Series(market + 5 + rng.normal(0, 3, 120), index=t),
        })
        assert abs(rec.offsets["croma"] - 40) < 8
        assert abs(rec.offsets["flipkart"] + 25) < 8

    def test_retailer_forecast_uses_offset(self):
        f = forecast_retailer(np.array([1000.0, 1010.0]), 1000.0, 35.0, 40)
        assert f[0] == pytest.approx(1035.0)
        f2 = forecast_retailer(np.array([1000.0]), 1000.0, 35.0, 0)  # too few samples
        assert f2[0] == pytest.approx(1000.0)

    def test_empty_inputs(self):
        rec = reconcile({})
        assert rec.market.empty and rec.offsets == {}


# ------------------------------------------------------------ engine integration
class TestEngineV11:
    def _series(self, n=200, seed=1):
        rng = np.random.default_rng(seed)
        y = 1000 * (1 + np.cumsum(rng.normal(0, 0.004, n)))
        return pd.Series(y, index=pd.date_range("2025-01-01", periods=n, freq="D"))

    def test_three_part_confidence_present(self, tmp_path):
        eng = PredictionEngine(registry_dir=str(tmp_path / "reg"), calibration_dir=str(tmp_path / "cal"))
        fc = eng.forecast_from_series(self._series(), 24 * 7, category="headphones")
        conf = fc.confidence
        for key in ("forecast_confidence", "model_reliability", "data_reliability", "weights"):
            assert key in conf
        assert 0.0 <= conf["score"] <= 1.0
        assert conf["weights"] == {"forecast": 0.40, "model": 0.35, "data": 0.25}

    def test_data_tier_reduces_confidence(self, tmp_path):
        eng = PredictionEngine(registry_dir=str(tmp_path / "r"), calibration_dir=str(tmp_path / "c"))
        good = eng.forecast_from_series(self._series(), 24 * 7, data_tier="TRUSTED", match_confidence=1.0, quality_score=1.0)
        bad = eng.forecast_from_series(self._series(), 24 * 7, data_tier="QUARANTINED", match_confidence=0.3, quality_score=0.2)
        assert bad.confidence["data_reliability"] < good.confidence["data_reliability"]
        assert bad.confidence["score"] < good.confidence["score"]

    def test_model_version_comes_from_registry_champion(self, tmp_path):
        reg_dir = tmp_path / "reg"
        reg = ModelRegistry(reg_dir)
        reg.register(ModelRegistryEntry(model_id="champ-v42", name="champ", status="CHAMPION", category="headphones"))
        eng = PredictionEngine(registry_dir=str(reg_dir), calibration_dir=str(tmp_path / "cal"))
        fc = eng.forecast_from_series(self._series(), 24, category="headphones")
        assert fc.model_version == "champ-v42"

    def test_hierarchical_calibration_applied_in_target(self, tmp_path):
        cal_dir = tmp_path / "cal"
        store = CalibrationStore(cal_dir)
        rng = np.random.default_rng(12)
        pr = np.clip(rng.uniform(0, 1, 200) + 0.15, 0, 1)
        store.save_fit(pr, (pr > 0.5).astype(int), "headphones:168")
        eng = PredictionEngine(registry_dir=str(tmp_path / "r"), calibration_dir=str(cal_dir))
        probs, fc, warnings = eng.target_probabilities_from_series(
            self._series(), 950.0, [24 * 7], category="headphones", regime="NORMAL", retailer="croma"
        )
        assert fc.calibration_key_used == "headphones:168"
        assert 0.0 <= probs["7d"] <= 1.0

    def test_conformal_bucket_reported(self, tmp_path):
        conf_dir = tmp_path / "conf"
        store = RegimeConformalStore(conf_dir)
        rng = np.random.default_rng(13)
        store.fit_bucket(1, "NORMAL", np.abs(rng.normal(100, 20, 60)), 0.9)
        store.save()
        eng = PredictionEngine(registry_dir=str(tmp_path / "r"), calibration_dir=str(tmp_path / "c"),
                               conformal_dir=str(conf_dir))
        fc = eng.forecast_from_series(self._series(), 24, regime="NORMAL")
        assert fc.conformal_bucket_used == "NORMAL"
        assert fc.interval["lower"] < fc.interval["upper"]
