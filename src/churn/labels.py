"""Churn label construction — the single source of truth for the
definition in docs/target_definition.md. EDA notebooks reimplemented
this ad hoc for exploration; this module is what modeling actually
trains against, and is leakage-tested (label horizon reads
`order_date > as_of`, same boundary as src/features)."""

from __future__ import annotations

import pandas as pd

QUALIFYING_STATUS = "completed"


def compute_churn_labels(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    as_of: pd.Timestamp,
    horizon_days: int = 90,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    """Returns one row per customer who is ELIGIBLE for a churn label at
    `as_of` (i.e. had a qualifying order in the `active_lookback_days`
    before it) with columns [customer_id, churned]. Customers who
    weren't active at the cutoff are simply absent — churn isn't a
    well-posed question for them at this cutoff (see
    docs/target_definition.md)."""
    as_of = pd.Timestamp(as_of)
    qualifying = orders[orders["status"] == QUALIFYING_STATUS]

    lookback_start = as_of - pd.Timedelta(days=active_lookback_days)
    horizon_end = as_of + pd.Timedelta(days=horizon_days)

    active_ids = set(
        qualifying[(qualifying["order_date"] > lookback_start) & (qualifying["order_date"] <= as_of)]["customer_id"]
    )
    future_ids = set(
        qualifying[(qualifying["order_date"] > as_of) & (qualifying["order_date"] <= horizon_end)]["customer_id"]
    )

    eligible = customers[customers["customer_id"].isin(active_ids)][["customer_id"]].copy()
    eligible["churned"] = (~eligible["customer_id"].isin(future_ids)).astype(int)
    return eligible.reset_index(drop=True)
