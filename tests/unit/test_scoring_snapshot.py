import pandas as pd
import pytest

from churn.dataset import build_snapshot as build_labeled_snapshot
from data import config
from scoring.snapshot import build_scoring_snapshot, latest_data_day, resolve_score_as_of

CUTOFF = pd.Timestamp(config.OBSERVATION_CUTOFF)


def _args(d):
    return d["customers"], d["orders"], d["interactions"], d["support"], d["products"]


def test_matches_labeled_snapshot_customers_and_features_at_the_cutoff(dataset):
    scoring = build_scoring_snapshot(*_args(dataset), CUTOFF)
    labeled = build_labeled_snapshot(*_args(dataset), CUTOFF)
    labeled_features = labeled.drop(columns=["churned", "snapshot_cutoff"])
    scoring = scoring.sort_values("customer_id").reset_index(drop=True)
    labeled_features = labeled_features.sort_values("customer_id").reset_index(drop=True)
    assert "churned" not in scoring.columns
    pd.testing.assert_frame_equal(scoring, labeled_features[scoring.columns], check_dtype=False)


def test_only_customers_with_a_completed_order_in_the_lookback_are_eligible(dataset):
    orders = dataset["orders"]
    window_start = CUTOFF - pd.Timedelta(days=180)
    in_window = (orders["order_date"] > window_start) & (orders["order_date"] <= CUTOFF)
    expected = set(orders[in_window & (orders["status"] == "completed")]["customer_id"])
    scored = set(build_scoring_snapshot(*_args(dataset), CUTOFF)["customer_id"])
    assert scored == expected

    # Make one eligible customer's orders in the window all refunded: they must drop out.
    victim = sorted(expected)[0]
    changed = orders.copy()
    changed.loc[in_window & (changed["customer_id"] == victim), "status"] = "refunded"
    customers, _, interactions, support, products = _args(dataset)
    rescored = set(build_scoring_snapshot(customers, changed, interactions, support, products, CUTOFF)["customer_id"])
    assert victim not in rescored

    # A customer whose last completed order is older than the lookback is not eligible.
    stale = set(orders[orders["status"] == "completed"]["customer_id"]) - expected
    assert stale, "fixture should contain customers active before the window but not in it"
    assert scored.isdisjoint(stale)


def test_rows_after_the_scoring_date_do_not_change_the_snapshot(dataset):
    base = build_scoring_snapshot(*_args(dataset), CUTOFF)

    orders = dataset["orders"].copy()
    later = orders["order_date"] > CUTOFF
    assert later.any()
    orders.loc[later, "amount"] = orders.loc[later, "amount"] * 10
    orders = orders[~(later & (orders.index % 2 == 0))]
    interactions = dataset["interactions"][dataset["interactions"]["event_time"] <= CUTOFF]
    perturbed = build_scoring_snapshot(
        dataset["customers"], orders, interactions, dataset["support"], dataset["products"], CUTOFF
    )

    pd.testing.assert_frame_equal(base, perturbed)


def test_scoring_date_before_all_data_returns_an_empty_frame(dataset):
    snap = build_scoring_snapshot(*_args(dataset), pd.Timestamp("2023-01-01"))
    assert snap.empty
    assert "customer_id" in snap.columns


def test_latest_data_day_is_midnight_of_the_newest_timestamp_across_tables():
    orders = pd.DataFrame({"order_date": pd.to_datetime(["2026-01-01 10:00", "2026-03-05 23:59"])})
    interactions = pd.DataFrame({"event_time": pd.to_datetime(["2026-03-06 00:30"])})
    support = pd.DataFrame({"created_at": pd.to_datetime([])})
    assert latest_data_day(orders, interactions, support) == pd.Timestamp("2026-03-06")


def test_latest_data_day_raises_when_everything_is_empty():
    empty = pd.DataFrame({"order_date": pd.to_datetime([])})
    with pytest.raises(ValueError, match="empty"):
        latest_data_day(empty, pd.DataFrame({"event_time": pd.to_datetime([])}), pd.DataFrame({"created_at": pd.to_datetime([])}))


def test_resolve_score_as_of_prefers_the_requested_date_and_normalizes_it():
    orders = pd.DataFrame({"order_date": pd.to_datetime(["2026-03-05"])})
    empty_i = pd.DataFrame({"event_time": pd.to_datetime([])})
    empty_s = pd.DataFrame({"created_at": pd.to_datetime([])})
    assert resolve_score_as_of("2025-12-31", orders, empty_i, empty_s) == pd.Timestamp("2025-12-31")
    assert resolve_score_as_of(None, orders, empty_i, empty_s) == pd.Timestamp("2026-03-05")


def test_resolve_score_as_of_rejects_a_malformed_date():
    orders = pd.DataFrame({"order_date": pd.to_datetime(["2026-03-05"])})
    empty_i = pd.DataFrame({"event_time": pd.to_datetime([])})
    empty_s = pd.DataFrame({"created_at": pd.to_datetime([])})
    with pytest.raises(ValueError):
        resolve_score_as_of("not-a-date", orders, empty_i, empty_s)
