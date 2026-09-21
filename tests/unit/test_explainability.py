from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.train import train_xgboost
from explainability.shap_utils import (
    compute_shap_values,
    global_importance,
    importance_by_segment,
    local_explanation,
    top_drivers,
)


@pytest.fixture
def toy_model_and_data():
    rng = np.random.default_rng(0)
    n = 300
    X = pd.DataFrame(
        {
            "country": rng.choice(["IN", "US"], size=n),
            "plan": rng.choice(["bronze", "gold"], size=n),
            "recency_days": rng.normal(50, 20, size=n),
            "frequency": rng.integers(0, 30, size=n),
        }
    )
    # churn driven almost entirely by high recency -- an unambiguous ground truth
    y = pd.Series((X["recency_days"] > 55).astype(int), name="churned")
    model = train_xgboost(X, y)
    return model, X, y


class TestShapComputation:
    def test_shap_values_shape_matches_transformed_features(self, toy_model_and_data):
        model, X, _ = toy_model_and_data
        shap_values, X_transformed, feature_names = compute_shap_values(model, X)
        assert shap_values.shape == X_transformed.shape
        assert shap_values.shape[1] == len(feature_names)

    def test_recency_is_the_top_global_driver(self, toy_model_and_data):
        model, X, _ = toy_model_and_data
        shap_values, _, feature_names = compute_shap_values(model, X)
        importance = global_importance(shap_values, feature_names)
        assert importance.index[0] == "numeric__recency_days"

    def test_high_recency_pushes_toward_churn(self, toy_model_and_data):
        model, X, _ = toy_model_and_data
        shap_values, X_transformed, feature_names = compute_shap_values(model, X)
        increases_risk, _ = top_drivers(shap_values, X_transformed, feature_names, n=3)
        # recency should show up on the "higher value -> more churn risk" side
        assert "numeric__recency_days" in increases_risk.index


class TestLocalExplanation:
    def test_returns_one_row_per_feature_sorted_by_impact(self, toy_model_and_data):
        model, X, _ = toy_model_and_data
        shap_values, X_transformed, feature_names = compute_shap_values(model, X)
        explanation = local_explanation(shap_values, feature_names, row_index=0, X_transformed=X_transformed)
        assert len(explanation) == len(feature_names)
        abs_vals = explanation["shap_value"].abs()
        assert list(abs_vals) == sorted(abs_vals, reverse=True)


class TestImportanceBySegment:
    def test_returns_one_row_per_segment_value(self, toy_model_and_data):
        model, X, _ = toy_model_and_data
        shap_values, _, feature_names = compute_shap_values(model, X)
        result = importance_by_segment(shap_values, feature_names, X["plan"], top_n=4)
        assert set(result.index) == {"bronze", "gold"}
        assert result.shape[1] == 4
