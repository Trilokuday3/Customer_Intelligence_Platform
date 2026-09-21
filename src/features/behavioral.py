"""Point-in-time behavioral features beyond RFM: rolling windows, trend
ratios, purchase-interval stats, category breadth, support/interaction
activity. Every function takes an explicit `as_of` and only reads rows
at or before it — see tests/unit/test_features.py for the leakage
guarantee (a full-dataset future-perturbation test, not just window
boundary checks).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

QUALIFYING_STATUS = "completed"


def _qualifying(orders: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    return orders[(orders["status"] == QUALIFYING_STATUS) & (orders["order_date"] <= as_of)]


def tenure_days(customers: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    as_of = pd.Timestamp(as_of)
    return (as_of - customers["signup_date"]).dt.days.rename("tenure_days")


def rolling_order_stats(
    orders: pd.DataFrame, customer_ids: pd.Series, as_of: pd.Timestamp, windows: tuple[int, ...] = (30, 60, 90, 180)
) -> pd.DataFrame:
    """Order count and revenue in each trailing window ending at `as_of`."""
    as_of = pd.Timestamp(as_of)
    qualifying = _qualifying(orders, as_of)
    out = pd.DataFrame(index=pd.Index(customer_ids, name="customer_id"))

    for window in windows:
        start = as_of - pd.Timedelta(days=window)
        in_window = qualifying[qualifying["order_date"] > start]
        agg = in_window.groupby("customer_id").agg(
            **{
                f"order_count_{window}d": ("order_id", "count"),
                f"revenue_{window}d": ("amount", "sum"),
            }
        )
        out = out.join(agg)

    count_cols = [c for c in out.columns if c.startswith("order_count_")]
    revenue_cols = [c for c in out.columns if c.startswith("revenue_")]
    out[count_cols] = out[count_cols].fillna(0).astype(int)
    out[revenue_cols] = out[revenue_cols].fillna(0.0)
    return out.reset_index()


def engagement_trend(
    orders: pd.DataFrame,
    customer_ids: pd.Series,
    as_of: pd.Timestamp,
    recent_days: int = 30,
    baseline_days: int = 180,
) -> pd.DataFrame:
    """Ratio of recent daily order rate to the customer's own baseline
    daily rate over a longer prior window. > 1 means accelerating,
    < 1 means decelerating (a leading churn indicator — see
    docs/eda_report.md)."""
    as_of = pd.Timestamp(as_of)
    qualifying = _qualifying(orders, as_of)
    recent_start = as_of - pd.Timedelta(days=recent_days)
    baseline_start = as_of - pd.Timedelta(days=baseline_days)

    recent_count = qualifying[qualifying["order_date"] > recent_start].groupby("customer_id").size()
    baseline_count = qualifying[
        (qualifying["order_date"] > baseline_start) & (qualifying["order_date"] <= recent_start)
    ].groupby("customer_id").size()

    out = pd.DataFrame(index=pd.Index(customer_ids, name="customer_id"))
    out["recent_order_rate"] = (recent_count / recent_days).reindex(out.index).fillna(0.0)
    baseline_days_span = baseline_days - recent_days
    out["baseline_order_rate"] = (baseline_count / baseline_days_span).reindex(out.index).fillna(0.0)
    out["engagement_ratio"] = out["recent_order_rate"] / (out["baseline_order_rate"] + 1e-3)
    return out.reset_index()


def purchase_interval_stats(orders: pd.DataFrame, customer_ids: pd.Series, as_of: pd.Timestamp) -> pd.DataFrame:
    """Mean/std of days between consecutive qualifying orders, up to
    `as_of`. Customers with 0 or 1 qualifying order get NaN (undefined
    interval) rather than 0, so downstream imputation is a deliberate
    choice, not an accidental zero."""
    as_of = pd.Timestamp(as_of)
    qualifying = _qualifying(orders, as_of).sort_values(["customer_id", "order_date"])

    def _intervals(group: pd.DataFrame) -> pd.Series:
        diffs = group["order_date"].diff().dt.days.dropna()
        if diffs.empty:
            return pd.Series({"interval_mean_days": np.nan, "interval_std_days": np.nan})
        return pd.Series({"interval_mean_days": diffs.mean(), "interval_std_days": diffs.std()})

    stats = qualifying.groupby("customer_id").apply(_intervals, include_groups=False)
    out = pd.DataFrame(index=pd.Index(customer_ids, name="customer_id")).join(stats)
    return out.reset_index()


def category_breadth(
    orders: pd.DataFrame, products: pd.DataFrame, customer_ids: pd.Series, as_of: pd.Timestamp
) -> pd.DataFrame:
    """Distinct product categories a customer has bought from, up to `as_of`."""
    as_of = pd.Timestamp(as_of)
    qualifying = _qualifying(orders, as_of).merge(products[["product_id", "category"]], on="product_id")
    breadth = qualifying.groupby("customer_id")["category"].nunique().rename("category_breadth")
    out = pd.DataFrame(index=pd.Index(customer_ids, name="customer_id")).join(breadth)
    out["category_breadth"] = out["category_breadth"].fillna(0).astype(int)
    return out.reset_index()


def support_features(
    support: pd.DataFrame, customer_ids: pd.Series, as_of: pd.Timestamp, windows: tuple[int, ...] = (90, 180)
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    hist = support[support["created_at"] <= as_of]
    out = pd.DataFrame(index=pd.Index(customer_ids, name="customer_id"))

    for window in windows:
        start = as_of - pd.Timedelta(days=window)
        count = hist[hist["created_at"] > start].groupby("customer_id").size()
        out[f"ticket_count_{window}d"] = count.reindex(out.index).fillna(0).astype(int)

    cancellation_count = hist[hist["category"] == "cancellation_request"].groupby("customer_id").size()
    out["cancellation_ticket_count"] = cancellation_count.reindex(out.index).fillna(0).astype(int)
    return out.reset_index()


def payment_behavior(orders: pd.DataFrame, customer_ids: pd.Series, as_of: pd.Timestamp) -> pd.DataFrame:
    """Refund/cancellation rate among ALL orders (not just qualifying
    ones — this is exactly the signal that "qualifying" excludes
    elsewhere, so it belongs here as its own feature)."""
    as_of = pd.Timestamp(as_of)
    hist = orders[orders["order_date"] <= as_of]
    out = pd.DataFrame(index=pd.Index(customer_ids, name="customer_id"))

    total = hist.groupby("customer_id").size()
    non_qualifying = hist[hist["status"] != QUALIFYING_STATUS].groupby("customer_id").size()
    out["total_order_count"] = total.reindex(out.index).fillna(0).astype(int)
    out["non_qualifying_count"] = non_qualifying.reindex(out.index).fillna(0).astype(int)
    out["refund_cancel_rate"] = (out["non_qualifying_count"] / out["total_order_count"].replace(0, np.nan)).fillna(0.0)
    return out.reset_index()


def build_feature_matrix(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    products: pd.DataFrame,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Assembles one row per customer: identity/categorical columns plus
    every point-in-time feature above, all computed as of the same
    cutoff. Does NOT include the churn/CLV label — see src/churn (Phase 5)
    / src/clv (Phase 6) for label construction, kept as a separate step
    so a feature-matrix bug can never silently leak the label in."""
    as_of = pd.Timestamp(as_of)
    from features.rfm import compute_rfm  # local import avoids a hard cycle if rfm grows to need behavioral later

    ids = customers["customer_id"]
    feature_frames = [
        customers[["customer_id", "country", "acquisition_channel", "plan"]].copy(),
        tenure_days(customers, as_of).to_frame().assign(customer_id=customers["customer_id"].values),
        compute_rfm(orders, customers, as_of=as_of),
        rolling_order_stats(orders, ids, as_of),
        engagement_trend(orders, ids, as_of),
        purchase_interval_stats(orders, ids, as_of),
        category_breadth(orders, products, ids, as_of),
        support_features(support, ids, as_of),
        payment_behavior(orders, ids, as_of),
    ]

    matrix = feature_frames[0]
    for frame in feature_frames[1:]:
        matrix = matrix.merge(frame, on="customer_id", how="left")
    return matrix
