from __future__ import annotations

import pandas as pd

from churn.labels import compute_churn_labels

CUTOFF = pd.Timestamp("2025-12-31")


def _orders(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["order_date"] = pd.to_datetime(df["order_date"])
    if "status" not in df.columns:
        df["status"] = "completed"
    if "order_id" not in df.columns:
        df["order_id"] = [f"O{i}" for i in range(len(df))]
    return df


def _customers(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"customer_id": ids})


class TestEligibility:
    def test_inactive_customer_is_excluded_entirely(self):
        # last order 400 days before cutoff -> not "active" (180d lookback)
        orders = _orders([{"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=400), "amount": 1.0}])
        labels = compute_churn_labels(_customers(["C1"]), orders, CUTOFF)
        assert labels.empty

    def test_active_customer_with_future_order_is_not_churned(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=30), "amount": 1.0},
            ]
        )
        labels = compute_churn_labels(_customers(["C1"]), orders, CUTOFF).set_index("customer_id")
        assert labels.loc["C1", "churned"] == 0

    def test_active_customer_with_no_future_order_is_churned(self):
        orders = _orders([{"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0}])
        labels = compute_churn_labels(_customers(["C1"]), orders, CUTOFF).set_index("customer_id")
        assert labels.loc["C1", "churned"] == 1


class TestBoundaries:
    def test_order_beyond_horizon_does_not_save_from_churn(self):
        horizon_days = 90
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=horizon_days + 5), "amount": 1.0},
            ]
        )
        labels = compute_churn_labels(_customers(["C1"]), orders, CUTOFF, horizon_days=horizon_days).set_index(
            "customer_id"
        )
        assert labels.loc["C1", "churned"] == 1

    def test_non_qualifying_future_order_does_not_count_as_retention(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0, "status": "completed"},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=5), "amount": 1.0, "status": "refunded"},
            ]
        )
        labels = compute_churn_labels(_customers(["C1"]), orders, CUTOFF).set_index("customer_id")
        assert labels.loc["C1", "churned"] == 1

    def test_never_purchased_customer_is_not_eligible(self):
        orders = _orders([{"customer_id": "C2", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0}])
        labels = compute_churn_labels(_customers(["C1", "C2"]), orders, CUTOFF)
        assert "C1" not in set(labels["customer_id"])
