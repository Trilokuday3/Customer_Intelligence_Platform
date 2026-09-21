from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from segmentation.cluster import fit_kmeans, name_segments_from_profile, prepare_matrix, profile_clusters, select_k


@pytest.fixture
def toy_features():
    rng = np.random.default_rng(0)
    # two well-separated blobs so clustering has an obvious right answer
    blob_a = rng.normal(loc=0, scale=0.5, size=(50, 3))
    blob_b = rng.normal(loc=20, scale=0.5, size=(50, 3))
    data = np.vstack([blob_a, blob_b])
    df = pd.DataFrame(data, columns=["recency_days", "frequency", "monetary"])
    df["order_count_90d"] = 0
    df["revenue_90d"] = 0.0
    df["engagement_ratio"] = 0.0
    # half missing, half real values -- exercises imputation without
    # hitting sklearn's all-NaN-column edge case (which just drops the column)
    df["interval_mean_days"] = [np.nan if i % 2 == 0 else 30.0 for i in range(100)]
    df["category_breadth"] = 0
    df["tenure_days"] = 0
    df["customer_id"] = [f"C{i}" for i in range(len(df))]
    return df


class TestPrepareMatrix:
    def test_imputes_and_scales(self, toy_features):
        X_scaled, pipeline = prepare_matrix(toy_features)
        assert X_scaled.shape == (100, 9)
        assert not np.isnan(X_scaled).any()

    def test_custom_feature_columns(self, toy_features):
        X_scaled, _ = prepare_matrix(toy_features, feature_cols=["recency_days", "frequency"])
        assert X_scaled.shape == (100, 2)


class TestSelectK:
    def test_returns_one_row_per_k_with_valid_silhouette(self, toy_features):
        X_scaled, _ = prepare_matrix(toy_features)
        results = select_k(X_scaled, k_range=range(2, 5))
        assert list(results["k"]) == [2, 3, 4]
        assert results["silhouette"].between(-1, 1).all()

    def test_two_separated_blobs_favor_k_equals_two(self, toy_features):
        X_scaled, _ = prepare_matrix(toy_features)
        results = select_k(X_scaled, k_range=range(2, 5)).set_index("k")
        assert results["silhouette"].idxmax() == 2


class TestFitKmeans:
    def test_recovers_two_separated_clusters(self, toy_features):
        X_scaled, _ = prepare_matrix(toy_features)
        km = fit_kmeans(X_scaled, k=2)
        assert len(set(km.labels_)) == 2
        # each true blob (rows 0-49 vs 50-99) should land in its own cluster
        assert len(set(km.labels_[:50])) == 1
        assert len(set(km.labels_[50:])) == 1
        assert km.labels_[0] != km.labels_[50]


class TestProfileClusters:
    def test_aggregates_by_cluster(self, toy_features):
        toy_features["cluster"] = [0] * 50 + [1] * 50
        churn = pd.DataFrame({"customer_id": toy_features["customer_id"], "churned": [0] * 50 + [1] * 50})
        profile = profile_clusters(toy_features, churn_labels=churn)
        assert set(profile.index) == {0, 1}
        assert profile.loc[0, "size"] == 50
        assert profile.loc[1, "churned"] == pytest.approx(1.0)
        assert profile.loc[0, "monetary"] < profile.loc[1, "monetary"]


class TestNameSegmentsFromProfile:
    def test_names_every_cluster_uniquely_by_recency_and_tenure(self):
        profile = pd.DataFrame(
            {
                "recency_days": [10.0, 60.0, 400.0, 70.0],
                "tenure_days": [500.0, 500.0, 600.0, 200.0],
            },
            index=[0, 1, 2, 3],
        )
        names = name_segments_from_profile(profile)
        assert names[0] == "Champions"  # lowest recency
        assert names[2] == "Dormant / Lost"  # highest recency
        assert names[3] == "New / Developing"  # shortest tenure among what's left
        assert names[1] == "Steady Regulars"  # whatever remains
        assert len(set(names.values())) == 4
