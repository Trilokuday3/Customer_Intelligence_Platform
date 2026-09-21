"""Forward-looking CLV label: total qualifying revenue in the CLV
horizon after `as_of` (see docs/target_definition.md). Same eligibility
population as churn (`active_lookback_days` before cutoff) so churn and
CLV snapshots line up customer-for-customer — useful later for the
"high-value at-risk" cut in Customer 360 / the decision layer.

A customer who churns necessarily gets `future_clv == 0` for this
horizon by construction (no future qualifying orders => no future
revenue) — that's a real, expected relationship between the two labels,
not a bug.
"""

from __future__ import annotations

import pandas as pd

QUALIFYING_STATUS = "completed"


def compute_clv_labels(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    as_of: pd.Timestamp,
    horizon_days: int = 180,
    active_lookback_days: int = 180,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    qualifying = orders[orders["status"] == QUALIFYING_STATUS]

    lookback_start = as_of - pd.Timedelta(days=active_lookback_days)
    horizon_end = as_of + pd.Timedelta(days=horizon_days)

    active_ids = set(
        qualifying[(qualifying["order_date"] > lookback_start) & (qualifying["order_date"] <= as_of)]["customer_id"]
    )
    future_revenue = (
        qualifying[(qualifying["order_date"] > as_of) & (qualifying["order_date"] <= horizon_end)]
        .groupby("customer_id")["amount"]
        .sum()
    )

    eligible = customers[customers["customer_id"].isin(active_ids)][["customer_id"]].copy()
    eligible["future_clv"] = eligible["customer_id"].map(future_revenue).fillna(0.0)
    return eligible.reset_index(drop=True)


def historical_clv(orders: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    """Descriptive only — cumulative net revenue through `as_of`. Never
    use this as a model feature for predicting the same period's future
    value (it's the "have already gotten" number, not a predictor)."""
    as_of = pd.Timestamp(as_of)
    qualifying = orders[(orders["status"] == QUALIFYING_STATUS) & (orders["order_date"] <= as_of)]
    return qualifying.groupby("customer_id")["amount"].sum().rename("historical_clv")
