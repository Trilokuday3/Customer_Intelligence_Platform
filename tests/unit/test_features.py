"""Feature-engineering tests. TestNoLeakageUnderFuturePerturbation is the
important one: it doesn't just check a few hand-picked boundary cases,
it corrupts every row after the cutoff across all three event tables and
asserts the entire feature matrix is byte-for-byte unchanged. If any
function in src/features ever accidentally reads past `as_of`, this
test fails regardless of which feature it was.
"""

from __future__ import annotations

import pandas as pd
import pytest

from features.behavioral import (
    build_feature_matrix,
    category_breadth,
    payment_behavior,
    purchase_interval_stats,
    rolling_order_stats,
)

CUTOFF = pd.Timestamp("2025-12-31")


def _orders(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["order_date"] = pd.to_datetime(df["order_date"])
    if "status" not in df.columns:
        df["status"] = "completed"
    if "order_id" not in df.columns:
        df["order_id"] = [f"O{i}" for i in range(len(df))]
    if "product_id" not in df.columns:
        df["product_id"] = "P0"
    return df


class TestRollingWindowBoundary:
    def test_order_exactly_at_window_start_is_excluded(self):
        # window is (as_of - 30d, as_of] -- an order exactly 30 days before
        # as_of falls ON the boundary and should be excluded (strictly >).
        boundary_date = CUTOFF - pd.Timedelta(days=30)
        orders = _orders([{"customer_id": "C1", "order_date": boundary_date, "amount": 100.0}])
        stats = rolling_order_stats(orders, pd.Series(["C1"]), CUTOFF, windows=(30,)).set_index("customer_id")
        assert stats.loc["C1", "order_count_30d"] == 0

    def test_order_one_day_inside_window_is_included(self):
        inside_date = CUTOFF - pd.Timedelta(days=29)
        orders = _orders([{"customer_id": "C1", "order_date": inside_date, "amount": 100.0}])
        stats = rolling_order_stats(orders, pd.Series(["C1"]), CUTOFF, windows=(30,)).set_index("customer_id")
        assert stats.loc["C1", "order_count_30d"] == 1
        assert stats.loc["C1", "revenue_30d"] == pytest.approx(100.0)

    def test_order_exactly_at_as_of_is_included(self):
        orders = _orders([{"customer_id": "C1", "order_date": CUTOFF, "amount": 50.0}])
        stats = rolling_order_stats(orders, pd.Series(["C1"]), CUTOFF, windows=(30,)).set_index("customer_id")
        assert stats.loc["C1", "order_count_30d"] == 1


class TestPurchaseIntervals:
    def test_two_orders_thirty_days_apart(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-11-01", "amount": 10.0},
                {"customer_id": "C1", "order_date": "2025-12-01", "amount": 10.0},
            ]
        )
        stats = purchase_interval_stats(orders, pd.Series(["C1"]), CUTOFF).set_index("customer_id")
        assert stats.loc["C1", "interval_mean_days"] == pytest.approx(30.0)

    def test_single_order_gives_nan_not_zero(self):
        orders = _orders([{"customer_id": "C1", "order_date": "2025-12-01", "amount": 10.0}])
        stats = purchase_interval_stats(orders, pd.Series(["C1"]), CUTOFF).set_index("customer_id")
        assert pd.isna(stats.loc["C1", "interval_mean_days"])


class TestPaymentBehavior:
    def test_refund_rate_counts_non_qualifying_against_all_orders(self):
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-12-01", "amount": 100.0, "status": "completed"},
                {"customer_id": "C1", "order_date": "2025-12-05", "amount": 50.0, "status": "refunded"},
                {"customer_id": "C1", "order_date": "2025-12-10", "amount": 20.0, "status": "cancelled"},
            ]
        )
        stats = payment_behavior(orders, pd.Series(["C1"]), CUTOFF).set_index("customer_id")
        assert stats.loc["C1", "total_order_count"] == 3
        assert stats.loc["C1", "non_qualifying_count"] == 2
        assert stats.loc["C1", "refund_cancel_rate"] == pytest.approx(2 / 3)


class TestCategoryBreadth:
    def test_counts_distinct_categories_only(self):
        products = pd.DataFrame(
            {"product_id": ["P1", "P2", "P3"], "category": ["electronics", "electronics", "books"], "price": [10, 20, 5]}
        )
        orders = _orders(
            [
                {"customer_id": "C1", "order_date": "2025-12-01", "amount": 10.0, "product_id": "P1"},
                {"customer_id": "C1", "order_date": "2025-12-02", "amount": 20.0, "product_id": "P2"},
                {"customer_id": "C1", "order_date": "2025-12-03", "amount": 5.0, "product_id": "P3"},
            ]
        )
        result = category_breadth(orders, products, pd.Series(["C1"]), CUTOFF).set_index("customer_id")
        assert result.loc["C1", "category_breadth"] == 2  # electronics + books, not 3


class TestNoLeakageUnderFuturePerturbation:
    """The strong, generic leakage test: corrupt everything after the
    cutoff and assert the feature matrix doesn't move at all."""

    def test_feature_matrix_unchanged_by_future_corruption(self, dataset):
        from data import config

        as_of = pd.Timestamp(config.OBSERVATION_CUTOFF)
        customers, orders, interactions, support, products = (
            dataset["customers"],
            dataset["orders"],
            dataset["interactions"],
            dataset["support"],
            dataset["products"],
        )

        baseline = build_feature_matrix(customers, orders, interactions, support, products, as_of)

        corrupted_orders = orders.copy()
        future_order_mask = corrupted_orders["order_date"] > as_of
        assert future_order_mask.any(), "test fixture must contain future orders to be meaningful"
        corrupted_orders.loc[future_order_mask, "amount"] = 999_999.0
        corrupted_orders.loc[future_order_mask, "status"] = "completed"
        corrupted_orders.loc[future_order_mask, "product_id"] = products["product_id"].iloc[0]

        corrupted_support = support.copy()
        future_support_mask = corrupted_support["created_at"] > as_of
        corrupted_support.loc[future_support_mask, "category"] = "cancellation_request"

        corrupted_interactions = interactions.copy()
        future_interaction_mask = corrupted_interactions["event_time"] > as_of
        corrupted_interactions.loc[future_interaction_mask, "event_type"] = "add_to_cart"

        perturbed = build_feature_matrix(
            customers, corrupted_orders, corrupted_interactions, corrupted_support, products, as_of
        )

        pd.testing.assert_frame_equal(baseline, perturbed)

    def test_feature_matrix_changes_when_past_data_changes(self, dataset):
        """Sanity check for the test above: prove the equality isn't
        trivial (e.g. from a function that ignores its inputs) by
        perturbing PAST data and confirming the matrix DOES change."""
        from data import config

        as_of = pd.Timestamp(config.OBSERVATION_CUTOFF)
        customers, orders, interactions, support, products = (
            dataset["customers"],
            dataset["orders"],
            dataset["interactions"],
            dataset["support"],
            dataset["products"],
        )

        baseline = build_feature_matrix(customers, orders, interactions, support, products, as_of)

        corrupted_orders = orders.copy()
        past_mask = corrupted_orders["order_date"] <= as_of
        corrupted_orders.loc[past_mask, "amount"] = corrupted_orders.loc[past_mask, "amount"] + 1_000_000.0

        perturbed = build_feature_matrix(customers, corrupted_orders, interactions, support, products, as_of)

        with pytest.raises(AssertionError):
            pd.testing.assert_frame_equal(baseline, perturbed)
