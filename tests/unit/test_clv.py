from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clv.evaluate import decile_table, evaluate_clv_model, high_value_capture_at_k
from clv.labels import compute_clv_labels, historical_clv

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


class TestClvLabels:
    def test_sums_qualifying_future_revenue_within_horizon(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0},  # makes them "active"
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=30), "amount": 100.0},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=170), "amount": 50.0},
            ]
        )
        labels = compute_clv_labels(_customers(["C1"]), orders, CUTOFF, horizon_days=180).set_index("customer_id")
        assert labels.loc["C1", "future_clv"] == pytest.approx(150.0)

    def test_order_beyond_horizon_excluded(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=200), "amount": 999.0},
            ]
        )
        labels = compute_clv_labels(_customers(["C1"]), orders, CUTOFF, horizon_days=180).set_index("customer_id")
        assert labels.loc["C1", "future_clv"] == pytest.approx(0.0)

    def test_non_qualifying_future_order_excluded(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 1.0, "status": "completed"},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=30), "amount": 999.0, "status": "refunded"},
            ]
        )
        labels = compute_clv_labels(_customers(["C1"]), orders, CUTOFF).set_index("customer_id")
        assert labels.loc["C1", "future_clv"] == pytest.approx(0.0)

    def test_inactive_customer_is_not_eligible(self):
        orders = _orders([{"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=400), "amount": 1.0}])
        labels = compute_clv_labels(_customers(["C1"]), orders, CUTOFF)
        assert labels.empty

    def test_historical_clv_excludes_future(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": CUTOFF - pd.Timedelta(days=10), "amount": 40.0},
                {"customer_id": "C1", "order_date": CUTOFF + pd.Timedelta(days=10), "amount": 999.0},
            ]
        )
        hist = historical_clv(orders, CUTOFF)
        assert hist.loc["C1"] == pytest.approx(40.0)


class TestClvEvaluation:
    def test_perfect_predictions_give_zero_error(self):
        y_true = pd.Series([10.0, 20.0, 30.0])
        metrics = evaluate_clv_model(y_true, y_true.to_numpy())
        assert metrics["mae"] == pytest.approx(0.0)
        assert metrics["rmse"] == pytest.approx(0.0)
        assert metrics["spearman_rank_corr"] == pytest.approx(1.0)

    def test_decile_table_orders_by_predicted_descending(self):
        y_true = pd.Series(np.arange(100))
        y_pred = np.arange(100)
        table = decile_table(y_true, y_pred, n_bins=10)
        assert table["mean_predicted"].is_monotonic_decreasing

    def test_high_value_capture_perfect_ranking(self):
        y_true = np.array([10, 20, 30, 1, 2])
        y_pred = np.array([10, 20, 30, 1, 2])
        assert high_value_capture_at_k(y_true, y_pred, k_fraction=0.4) == 1.0
