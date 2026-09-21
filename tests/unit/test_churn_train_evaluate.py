from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.evaluate import evaluate_churn_model, lift_at_k, precision_at_k, segment_performance
from churn.train import make_preprocessor, train_baseline, train_logistic_regression


@pytest.fixture
def toy_frame():
    rng = np.random.default_rng(0)
    n = 200
    X = pd.DataFrame(
        {
            "country": rng.choice(["IN", "US"], size=n),
            "acquisition_channel": rng.choice(["organic", "email"], size=n),
            "plan": rng.choice(["bronze", "gold"], size=n),
            "recency_days": rng.normal(50, 20, size=n),
            "frequency": rng.integers(0, 30, size=n),
        }
    )
    # make churn depend on recency so the logistic model has something real to learn
    y = pd.Series((X["recency_days"] > 55).astype(int), name="churned")
    return X, y


class TestBaseline:
    def test_predicts_constant_training_rate(self, toy_frame):
        X, y = toy_frame
        model = train_baseline(X, y)
        proba = model.predict_proba(X)
        assert np.allclose(proba[:, 1], y.mean())
        assert np.allclose(proba.sum(axis=1), 1.0)


class TestPreprocessor:
    def test_separates_categorical_and_numeric(self, toy_frame):
        X, _ = toy_frame
        pre = make_preprocessor(list(X.columns))
        transformed = pre.fit_transform(X)
        # 2 numeric cols + one-hot(country=2) + one-hot(channel=2) + one-hot(plan=2) = 8
        assert transformed.shape == (len(X), 8)


class TestLogisticRegression:
    def test_fits_and_predicts_valid_probabilities(self, toy_frame):
        X, y = toy_frame
        model = train_logistic_regression(X, y)
        proba = model.predict_proba(X)[:, 1]
        assert ((proba >= 0) & (proba <= 1)).all()
        # should beat a coin flip on data it was trained on, given real signal
        from sklearn.metrics import roc_auc_score

        assert roc_auc_score(y, proba) > 0.7


class TestRankingMetrics:
    def test_precision_at_k_perfect_ranking(self):
        y_true = np.array([1, 1, 0, 0, 0])
        y_score = np.array([0.9, 0.8, 0.3, 0.2, 0.1])
        assert precision_at_k(y_true, y_score, k_fraction=0.4) == 1.0

    def test_lift_at_k_above_one_for_good_ranking(self):
        y_true = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
        y_score = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
        lift = lift_at_k(y_true, y_score, k_fraction=0.2)
        assert lift == pytest.approx(5.0)  # 100% precision at top 20% vs 20% base rate


class TestEvaluateChurnModel:
    def test_returns_expected_keys_and_ranges(self, toy_frame):
        X, y = toy_frame
        model = train_logistic_regression(X, y)
        proba = model.predict_proba(X)[:, 1]
        metrics = evaluate_churn_model(y, proba)

        for key in ["roc_auc", "pr_auc", "precision", "recall", "f1", "brier_score"]:
            assert 0.0 <= metrics[key] <= 1.0
        assert metrics["true_positives"] + metrics["false_negatives"] == y.sum()


class TestSegmentPerformance:
    def test_breaks_down_by_segment(self, toy_frame):
        X, y = toy_frame
        model = train_logistic_regression(X, y)
        proba = model.predict_proba(X)[:, 1]
        result = segment_performance(y, proba, X["plan"])
        assert set(result["segment"]) == {"bronze", "gold"}
        assert result["n"].sum() == len(X)
