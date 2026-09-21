"""Point-in-time RFM: the reusable feature code guide section 9.1 asks
for, so notebooks and future model training compute RFM the same way
instead of drifting apart.

Every function here takes an explicit `as_of` cutoff and only reads
order rows with `order_date <= as_of` — this is the leakage boundary
tested in tests/unit/test_rfm.py.
"""

from __future__ import annotations

import pandas as pd

QUALIFYING_STATUS = "completed"


def qualifying_orders(orders: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    return orders[(orders["status"] == QUALIFYING_STATUS) & (orders["order_date"] <= as_of)]


def compute_rfm(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    as_of: pd.Timestamp,
    lookback_days: int | None = None,
) -> pd.DataFrame:
    """Recency (days since last qualifying order, as of `as_of`), frequency
    (qualifying order count), monetary (total qualifying revenue).

    If `lookback_days` is set, frequency/monetary are computed only over
    orders in the trailing window `(as_of - lookback_days, as_of]`;
    recency always looks across the customer's full history up to
    `as_of` (an order outside the lookback window still tells you when
    they last bought). Customers with zero qualifying orders in scope
    get `recency = NaN` (never purchased) and `frequency = monetary = 0`.
    """
    as_of = pd.Timestamp(as_of)
    qualifying = qualifying_orders(orders, as_of)

    recency_source = qualifying
    window_source = qualifying
    if lookback_days is not None:
        window_start = as_of - pd.Timedelta(days=lookback_days)
        window_source = qualifying[qualifying["order_date"] > window_start]

    last_order = recency_source.groupby("customer_id")["order_date"].max()
    recency_days = (as_of - last_order).dt.days

    agg = window_source.groupby("customer_id").agg(
        frequency=("order_id", "count"),
        monetary=("amount", "sum"),
    )

    rfm = pd.DataFrame(index=customers["customer_id"]).join(recency_days.rename("recency_days")).join(agg)
    rfm["frequency"] = rfm["frequency"].fillna(0).astype(int)
    rfm["monetary"] = rfm["monetary"].fillna(0.0)
    return rfm.reset_index()


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    """Quintile scores (1=worst, 5=best) and a standard rule-based segment
    label. Customers who never purchased (recency_days is NaN) score 1
    on recency and are labeled "Never Purchased" rather than forced into
    a quintile that assumes at least one order.
    """
    scored = rfm.copy()
    never_purchased = scored["recency_days"].isna()

    scored["r_score"] = pd.qcut(scored["recency_days"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype("float")
    scored["f_score"] = pd.qcut(scored["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype("float")
    scored["m_score"] = pd.qcut(scored["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype("float")
    scored.loc[never_purchased, ["r_score", "f_score", "m_score"]] = 1.0

    scored["rfm_score"] = scored["r_score"] + scored["f_score"] + scored["m_score"]
    scored["segment"] = scored.apply(_label_segment, axis=1)
    scored.loc[never_purchased, "segment"] = "Never Purchased"
    return scored


def _label_segment(row: pd.Series) -> str:
    r, f, m = row["r_score"], row["f_score"], row["m_score"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3:
        return "Loyal"
    if r >= 4 and f <= 2:
        return "New / Promising"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r <= 2 and f <= 2 and m <= 2:
        return "Hibernating"
    return "Needs Attention"
