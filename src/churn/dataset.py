"""Builds labeled training snapshots. A snapshot = point-in-time features
(src/features, leak-safe by construction) joined to a forward-looking
label (src/churn/labels, deliberately look-ahead) for one cutoff.

Multiple snapshots at different cutoffs give a much larger, still
leakage-safe training pool than one cutoff alone — but the SAME
customer can appear in more than one snapshot, so splitting by cutoff
(not randomly) is what keeps train/validation/test honest. See
docs/model_card.md "Validation strategy".
"""

from __future__ import annotations

import pandas as pd

from churn.labels import compute_churn_labels
from features.behavioral import build_feature_matrix

LABEL_COLUMN = "churned"
GROUP_COLUMN = "snapshot_cutoff"
ID_COLUMNS = ["customer_id", GROUP_COLUMN]
NON_FEATURE_COLUMNS = ID_COLUMNS + [LABEL_COLUMN]


def build_snapshot(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    products: pd.DataFrame,
    as_of: pd.Timestamp,
    horizon_days: int = 90,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    labels = compute_churn_labels(customers, orders, as_of, horizon_days, active_lookback_days)
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
    horizon_days: int = 90,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    snapshots = [
        build_snapshot(customers, orders, interactions, support, products, cutoff, horizon_days, active_lookback_days)
        for cutoff in cutoffs
    ]
    return pd.concat(snapshots, ignore_index=True)


def feature_columns(snapshot: pd.DataFrame) -> list[str]:
    return [c for c in snapshot.columns if c not in NON_FEATURE_COLUMNS]
