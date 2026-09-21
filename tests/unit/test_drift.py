import numpy as np
import pandas as pd

from monitoring.drift import (
    compute_feature_drift,
    compute_prediction_drift,
    drift_severity,
    population_stability_index,
)


class TestPopulationStabilityIndex:
    def test_identical_distributions_are_stable(self):
        rng = np.random.default_rng(42)
        reference = pd.Series(rng.normal(size=2000))
        current = pd.Series(rng.normal(size=2000))
        psi = population_stability_index(reference, current)
        assert psi < 0.05

    def test_shifted_distribution_scores_higher_than_identical(self):
        rng = np.random.default_rng(42)
        reference = pd.Series(rng.normal(loc=0, scale=1, size=2000))
        same = pd.Series(rng.normal(loc=0, scale=1, size=2000))
        shifted = pd.Series(rng.normal(loc=3, scale=1, size=2000))

        psi_same = population_stability_index(reference, same)
        psi_shifted = population_stability_index(reference, shifted)
        assert psi_shifted > psi_same
        assert psi_shifted > 0.25

    def test_empty_current_returns_zero_not_an_error(self):
        reference = pd.Series(np.arange(50, dtype=float))
        current = pd.Series([], dtype=float)
        assert population_stability_index(reference, current) == 0.0

    def test_too_few_reference_points_returns_zero(self):
        reference = pd.Series([1.0, 2.0, 3.0])
        current = pd.Series(np.arange(50, dtype=float))
        assert population_stability_index(reference, current) == 0.0


class TestDriftSeverity:
    def test_thresholds(self):
        assert drift_severity(0.05) == "stable"
        assert drift_severity(0.15) == "moderate"
        assert drift_severity(0.30) == "significant"


class TestComputeFeatureDrift:
    def test_skips_non_numeric_columns_and_flags_shifted_ones(self):
        rng = np.random.default_rng(7)
        reference = pd.DataFrame(
            {
                "recency_days": rng.normal(30, 10, 1000),
                "plan": rng.choice(["free", "pro"], 1000),
            }
        )
        current = pd.DataFrame(
            {
                "recency_days": rng.normal(90, 10, 1000),
                "plan": rng.choice(["free", "pro"], 1000),
            }
        )
        result = compute_feature_drift(reference, current, ["recency_days", "plan"])
        assert list(result["feature"]) == ["recency_days"]
        assert result.loc[0, "severity"] == "significant"
        assert result.loc[0, "current_mean"] > result.loc[0, "reference_mean"]


class TestComputePredictionDrift:
    def test_reports_mean_shift_direction(self):
        rng = np.random.default_rng(3)
        reference = rng.beta(2, 8, 1000)
        current = rng.beta(6, 4, 1000)
        result = compute_prediction_drift(reference, current)
        assert result["current_mean"] > result["reference_mean"]
        assert result["severity"] in {"moderate", "significant"}
