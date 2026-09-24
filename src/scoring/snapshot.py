"""Label-free scoring snapshots.

Training and evaluation need labeled data (90 days of future for churn, 180
for CLV), so they stay pinned to fixed cutoffs. Scoring only needs features
as of a date plus the same eligibility rule the labels use, so it can run at
the newest data day. Eligibility is taken from churn.labels.compute_churn_labels
(the single source of truth) rather than reimplemented, so a change to the
rule there moves training and scoring together.
"""

from __future__ import annotations

import pandas as pd

from churn.labels import compute_churn_labels
from features.behavioral import build_feature_matrix


def latest_data_day(orders: pd.DataFrame, interactions: pd.DataFrame, support: pd.DataFrame) -> pd.Timestamp:
    """Midnight of the day of the newest event across the three event tables.
    Midnight (not the exact timestamp) keeps prediction_date a plain date so
    /predict/* can reproduce the same as-of exactly; events on that final
    partial day fall after the boundary and are not used."""
    newest = [
        pd.to_datetime(orders["order_date"]).max(),
        pd.to_datetime(interactions["event_time"]).max(),
        pd.to_datetime(support["created_at"]).max(),
    ]
    present = [pd.Timestamp(ts) for ts in newest if pd.notna(ts)]
    if not present:
        raise ValueError("cannot pick a scoring date: orders, interactions and support are all empty")
    return max(present).normalize()


def resolve_score_as_of(
    requested: str | None, orders: pd.DataFrame, interactions: pd.DataFrame, support: pd.DataFrame
) -> pd.Timestamp:
    """The scoring date: an explicit `--as-of` value if given, else the newest data day."""
    if requested:
        return pd.Timestamp(requested).normalize()
    return latest_data_day(orders, interactions, support)


def build_scoring_snapshot(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    products: pd.DataFrame,
    as_of: pd.Timestamp,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    """One row per customer eligible for scoring at `as_of`, with the same
    point-in-time features the models were trained on and no label column."""
    as_of = pd.Timestamp(as_of)
    eligible = compute_churn_labels(customers, orders, as_of, active_lookback_days=active_lookback_days)["customer_id"]
    features = build_feature_matrix(customers, orders, interactions, support, products, as_of)
    return features[features["customer_id"].isin(eligible)].reset_index(drop=True)
