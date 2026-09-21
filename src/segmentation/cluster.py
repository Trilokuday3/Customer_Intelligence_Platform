"""Behavioral segmentation (guide section 13): transform/scale -> optional
PCA -> K-Means, with silhouette used as one diagnostic among several
(inertia elbow, cluster-size balance), never the sole reason to pick k.
Cluster profiling (profile_clusters) is what earns clusters a business
name — never assign meaning before calling it (section 36's warning).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_CLUSTERING_FEATURES = [
    "recency_days",
    "frequency",
    "monetary",
    "order_count_90d",
    "revenue_90d",
    "engagement_ratio",
    "interval_mean_days",
    "category_breadth",
    "tenure_days",
]


def prepare_matrix(feature_matrix: pd.DataFrame, feature_cols: list[str] | None = None) -> tuple[np.ndarray, Pipeline]:
    feature_cols = feature_cols or DEFAULT_CLUSTERING_FEATURES
    pipeline = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    X_scaled = pipeline.fit_transform(feature_matrix[feature_cols])
    return X_scaled, pipeline


def select_k(X_scaled: np.ndarray, k_range: range = range(2, 9), random_state: int = 42) -> pd.DataFrame:
    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(X_scaled)
        rows.append(
            {
                "k": k,
                "inertia": km.inertia_,
                "silhouette": silhouette_score(X_scaled, km.labels_),
                "min_cluster_size": pd.Series(km.labels_).value_counts().min(),
            }
        )
    return pd.DataFrame(rows)


def fit_kmeans(X_scaled: np.ndarray, k: int, random_state: int = 42) -> KMeans:
    return KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(X_scaled)


def fit_hierarchical(X_scaled: np.ndarray, k: int) -> np.ndarray:
    return AgglomerativeClustering(n_clusters=k).fit_predict(X_scaled)


def pca_projection(X_scaled: np.ndarray, n_components: int = 2, random_state: int = 42) -> tuple[np.ndarray, PCA]:
    pca = PCA(n_components=n_components, random_state=random_state)
    return pca.fit_transform(X_scaled), pca


def profile_clusters(
    customers_with_cluster: pd.DataFrame,
    churn_labels: pd.DataFrame | None = None,
    clv_labels: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per cluster: size, RFM summary, and (if provided) churn
    rate / mean future CLV — the evidence a business name should be based
    on, not assumed in advance."""
    df = customers_with_cluster.copy()
    if churn_labels is not None:
        df = df.merge(churn_labels[["customer_id", "churned"]], on="customer_id", how="left")
    if clv_labels is not None:
        df = df.merge(clv_labels[["customer_id", "future_clv"]], on="customer_id", how="left")

    agg = {
        "customer_id": "count",
        "recency_days": "mean",
        "frequency": "mean",
        "monetary": "mean",
        "engagement_ratio": "mean",
        "category_breadth": "mean",
        "tenure_days": "mean",
    }
    if "churned" in df.columns:
        agg["churned"] = "mean"
    if "future_clv" in df.columns:
        agg["future_clv"] = "mean"

    profile = df.groupby("cluster").agg(agg).rename(columns={"customer_id": "size"})
    return profile.sort_values("monetary", ascending=False)


def name_segments_from_profile(profile: pd.DataFrame) -> dict:
    """The k=4 naming rule validated in notebooks/07_segmentation.ipynb
    and docs/segmentation_report.md, promoted here once a second caller
    (scripts/build_backend_data.py) needed the same logic — extracting it
    before that would have been guessing at reuse that didn't exist yet.
    Requires `recency_days` and `tenure_days` columns (see profile_clusters)."""
    names: dict = {}
    names[profile["recency_days"].idxmin()] = "Champions"
    names[profile["recency_days"].idxmax()] = "Dormant / Lost"
    remaining = [c for c in profile.index if c not in names]
    if remaining:
        names[profile.loc[remaining, "tenure_days"].idxmin()] = "New / Developing"
    for c in [c for c in profile.index if c not in names]:
        names[c] = "Steady Regulars"
    return names
