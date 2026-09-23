"""Per-customer event rates estimated from *observable* history only.

Deliberately does not use generator.py's hidden base_activity_rate (dropped
by to_public_customers): a real ingestion system would only know what is
in the tables. Customers with no order/interaction in the last
`dormant_days` before `as_of` are treated as churned and get only the
floor rate (an occasional event, not silence). Callers should pass seed
history only (see restrict_to_history) so rates are identical across
producer restarts.
"""

from __future__ import annotations

import pandas as pd

RATE_FLOOR_PER_DAY = 0.001

_RATE_SOURCES = (
    ("orders_per_day", "orders"),
    ("interactions_per_day", "interactions"),
    ("support_per_day", "support"),
)


def estimate_customer_rates(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    as_of,
    dormant_days: int = 90,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    frames = {"orders": orders, "interactions": interactions, "support": support}
    out = customers[["customer_id", "signup_date"]].reset_index(drop=True)
    tenure_days = (as_of - pd.to_datetime(out["signup_date"])).dt.days.clip(lower=1)

    last_activity = pd.concat(
        [
            orders.groupby("customer_id")["order_date"].max(),
            interactions.groupby("customer_id")["event_time"].max(),
        ]
    ).groupby(level=0).max()
    last_seen = out["customer_id"].map(last_activity)
    dormant = last_seen.isna() | (last_seen < as_of - pd.Timedelta(days=dormant_days))

    for column, key in _RATE_SOURCES:
        counts = out["customer_id"].map(frames[key].groupby("customer_id").size()).fillna(0)
        rate = (counts / tenure_days).clip(lower=RATE_FLOOR_PER_DAY)
        out[column] = rate.where(~dormant, RATE_FLOOR_PER_DAY)

    return out[["customer_id", "orders_per_day", "interactions_per_day", "support_per_day"]]


def restrict_to_history(
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    as_of,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rows strictly before `as_of` (copies). Lets rates be estimated from the
    seed history only, so they do not drift as streamed events are stored."""
    as_of = pd.Timestamp(as_of)
    return (
        orders[orders["order_date"] < as_of].copy(),
        interactions[interactions["event_time"] < as_of].copy(),
        support[support["created_at"] < as_of].copy(),
    )
