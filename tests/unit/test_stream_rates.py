import pandas as pd
import pytest

from streaming.rate_estimation import RATE_FLOOR_PER_DAY, estimate_customer_rates, restrict_to_history

AS_OF = pd.Timestamp("2026-06-30")


def _frames():
    customers = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3"],
            "signup_date": pd.to_datetime(["2024-01-01", "2024-01-01", "2026-06-01"]),
        }
    )
    # C1: 10 recent orders (active). C2: 10 orders long ago (churned). C3: nothing.
    orders = pd.DataFrame(
        {
            "customer_id": ["C1"] * 10 + ["C2"] * 10,
            "order_date": pd.to_datetime(["2026-06-20"] * 10 + ["2024-02-01"] * 10),
        }
    )
    interactions = pd.DataFrame({"customer_id": ["C1"] * 30, "event_time": pd.to_datetime(["2026-06-25"] * 30)})
    support = pd.DataFrame({"customer_id": ["C1"], "created_at": pd.to_datetime(["2026-05-01"])})
    return customers, orders, interactions, support


def test_active_customer_rate_is_history_over_tenure():
    rates = estimate_customer_rates(*_frames(), as_of=AS_OF).set_index("customer_id")
    tenure = (AS_OF - pd.Timestamp("2024-01-01")).days
    assert rates.loc["C1", "orders_per_day"] == pytest.approx(10 / tenure)
    assert rates.loc["C1", "interactions_per_day"] == pytest.approx(30 / tenure)
    assert rates.loc["C1", "support_per_day"] == pytest.approx(1 / tenure)


def test_dormant_customer_is_not_resurrected():
    rates = estimate_customer_rates(*_frames(), as_of=AS_OF).set_index("customer_id")
    assert rates.loc["C2", "orders_per_day"] == RATE_FLOOR_PER_DAY
    assert rates.loc["C2", "interactions_per_day"] == RATE_FLOOR_PER_DAY


def test_zero_history_customer_gets_floor_not_zero():
    rates = estimate_customer_rates(*_frames(), as_of=AS_OF).set_index("customer_id")
    assert rates.loc["C3", ["orders_per_day", "interactions_per_day", "support_per_day"]].tolist() == [RATE_FLOOR_PER_DAY] * 3


def test_output_has_one_row_per_customer_and_no_rate_below_floor():
    rates = estimate_customer_rates(*_frames(), as_of=AS_OF)
    assert rates["customer_id"].tolist() == ["C1", "C2", "C3"]
    assert (rates[["orders_per_day", "interactions_per_day", "support_per_day"]] >= RATE_FLOOR_PER_DAY).all().all()


def test_restrict_to_history_excludes_rows_at_or_after_as_of():
    _, orders, interactions, support = _frames()
    orders = pd.concat([orders, pd.DataFrame({"customer_id": ["C1", "C1"], "order_date": pd.to_datetime([AS_OF, AS_OF + pd.Timedelta(days=1)])})])
    interactions = pd.concat([interactions, pd.DataFrame({"customer_id": ["C1"], "event_time": pd.to_datetime([AS_OF])})])
    support = pd.concat([support, pd.DataFrame({"customer_id": ["C1"], "created_at": pd.to_datetime([AS_OF + pd.Timedelta(hours=1)])})])
    h_orders, h_inter, h_support = restrict_to_history(orders, interactions, support, AS_OF)
    assert (h_orders["order_date"] < AS_OF).all() and len(h_orders) == 20
    assert (h_inter["event_time"] < AS_OF).all() and len(h_inter) == 30
    assert (h_support["created_at"] < AS_OF).all() and len(h_support) == 1
    h_orders.loc[:, "customer_id"] = "X"
    assert (orders["customer_id"] == "X").sum() == 0  # copy, not a view


def test_rates_are_stable_after_streamed_events_land():
    customers, orders, interactions, support = _frames()
    before = estimate_customer_rates(customers, *restrict_to_history(orders, interactions, support, AS_OF), as_of=AS_OF)

    streamed_orders = pd.DataFrame({"customer_id": ["C2"] * 3, "order_date": pd.to_datetime(["2026-06-30 05:00", "2026-07-05 00:00", "2026-08-01 00:00"])})
    streamed_inter = pd.DataFrame({"customer_id": ["C2"] * 2, "event_time": pd.to_datetime(["2026-06-30 06:00", "2026-07-06 00:00"])})
    orders2 = pd.concat([orders, streamed_orders], ignore_index=True)
    inter2 = pd.concat([interactions, streamed_inter], ignore_index=True)
    after = estimate_customer_rates(customers, *restrict_to_history(orders2, inter2, support, AS_OF), as_of=AS_OF)

    pd.testing.assert_frame_equal(before, after)
    assert after.set_index("customer_id").loc["C2", "orders_per_day"] == RATE_FLOOR_PER_DAY
