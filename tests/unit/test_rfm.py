from __future__ import annotations

import pandas as pd
import pytest

from features.rfm import compute_rfm, score_rfm

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


class TestBasicRfm:
    def test_known_values(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-12-01", "amount": 100.0},
                {"customer_id": "C1", "order_date": "2025-11-01", "amount": 50.0},
                {"customer_id": "C1", "order_date": "2025-12-20", "amount": 25.0},
            ]
        )
        rfm = compute_rfm(orders, _customers(["C1"]), as_of=CUTOFF).set_index("customer_id")

        assert rfm.loc["C1", "recency_days"] == (CUTOFF - pd.Timestamp("2025-12-20")).days
        assert rfm.loc["C1", "frequency"] == 3
        assert rfm.loc["C1", "monetary"] == pytest.approx(175.0)

    def test_customer_with_no_orders_is_nan_recency_zero_frequency(self):
        orders = _orders([{"customer_id": "C1", "order_date": "2025-12-01", "amount": 10.0}])
        rfm = compute_rfm(orders, _customers(["C1", "C2"]), as_of=CUTOFF).set_index("customer_id")

        assert pd.isna(rfm.loc["C2", "recency_days"])
        assert rfm.loc["C2", "frequency"] == 0
        assert rfm.loc["C2", "monetary"] == 0.0

    def test_non_qualifying_status_excluded(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-12-01", "amount": 100.0, "status": "completed"},
                {"customer_id": "C1", "order_date": "2025-12-15", "amount": 999.0, "status": "refunded"},
            ]
        )
        rfm = compute_rfm(orders, _customers(["C1"]), as_of=CUTOFF).set_index("customer_id")

        assert rfm.loc["C1", "frequency"] == 1
        assert rfm.loc["C1", "monetary"] == pytest.approx(100.0)
        # recency should reflect the completed order, not the later refunded one
        assert rfm.loc["C1", "recency_days"] == (CUTOFF - pd.Timestamp("2025-12-01")).days


class TestNoLeakage:
    def test_future_orders_do_not_affect_frequency_or_monetary(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-12-01", "amount": 100.0},
                {"customer_id": "C1", "order_date": "2026-01-15", "amount": 5000.0},  # after cutoff
            ]
        )
        rfm = compute_rfm(orders, _customers(["C1"]), as_of=CUTOFF).set_index("customer_id")

        assert rfm.loc["C1", "frequency"] == 1
        assert rfm.loc["C1", "monetary"] == pytest.approx(100.0)

    def test_future_orders_do_not_affect_recency(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-11-01", "amount": 100.0},
                {"customer_id": "C1", "order_date": "2026-02-01", "amount": 100.0},  # after cutoff
            ]
        )
        rfm = compute_rfm(orders, _customers(["C1"]), as_of=CUTOFF).set_index("customer_id")

        assert rfm.loc["C1", "recency_days"] == (CUTOFF - pd.Timestamp("2025-11-01")).days

    def test_lookback_window_excludes_orders_outside_window_but_not_recency(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2024-01-01", "amount": 100.0},  # old, outside 90d lookback
                {"customer_id": "C1", "order_date": "2025-12-15", "amount": 20.0},
            ]
        )
        rfm = compute_rfm(orders, _customers(["C1"]), as_of=CUTOFF, lookback_days=90).set_index("customer_id")

        assert rfm.loc["C1", "frequency"] == 1
        assert rfm.loc["C1", "monetary"] == pytest.approx(20.0)
        # recency looks at full history regardless of the lookback window
        assert rfm.loc["C1", "recency_days"] == (CUTOFF - pd.Timestamp("2025-12-15")).days


class TestScoring:
    def test_scores_are_in_valid_range_and_segments_are_known(self, dataset):
        from data import config

        rfm = compute_rfm(dataset["orders"], dataset["customers"], as_of=pd.Timestamp(config.OBSERVATION_CUTOFF))
        scored = score_rfm(rfm)

        assert scored["r_score"].dropna().between(1, 5).all()
        assert scored["f_score"].dropna().between(1, 5).all()
        assert scored["m_score"].dropna().between(1, 5).all()

        known_segments = {
            "Champions",
            "Loyal",
            "New / Promising",
            "At Risk",
            "Hibernating",
            "Needs Attention",
            "Never Purchased",
        }
        assert set(scored["segment"]) <= known_segments
