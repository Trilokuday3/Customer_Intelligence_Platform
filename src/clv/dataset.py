"""CLV snapshots — mirrors src/churn/dataset.py's design (point-in-time
features + forward label, multiple cutoffs for a time-aware split)."""

from __future__ import annotations

import pandas as pd

from clv.labels import compute_clv_labels
from features.behavioral import build_feature_matrix

LABEL_COLUMN = "future_clv"
GROUP_COLUMN = "snapshot_cutoff"
NON_FEATURE_COLUMNS = ["customer_id", GROUP_COLUMN, LABEL_COLUMN]


def build_snapshot(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    products: pd.DataFrame,
    as_of: pd.Timestamp,
    horizon_days: int = 180,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    labels = compute_clv_labels(customers, orders, as_of, horizon_days, active_lookback_days)
    features = build_feature_matrix(customers, orders, interactions, support, products, as_of)

    snapshot = labels.merge(features, on="customer_id", how="left")
    snapshot[GROUP_COLUMN] = as_of
    return snapshot


def build_training_pool(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    products: pd.DataFrame,
    cutoffs: list[pd.Timestamp],
    horizon_days: int = 180,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    snapshots = [
        build_snapshot(customers, orders, interactions, support, products, cutoff, horizon_days, active_lookback_days)
        for cutoff in cutoffs
    ]
    return pd.concat(snapshots, ignore_index=True)


def feature_columns(snapshot: pd.DataFrame) -> list[str]:
    return [c for c in snapshot.columns if c not in NON_FEATURE_COLUMNS]
