import json

import numpy as np
import pandas as pd

from streaming.events import TOPICS, next_ids_from_frames, sample_tick_events, stream_start_time

PRICES = {"P00001": 10.0, "P00002": 25.5}
START = pd.Timestamp("2026-06-30 00:00:00")


def _rates(n=50, per_day=5.0):
    return pd.DataFrame(
        {
            "customer_id": [f"C{i:06d}" for i in range(n)],
            "orders_per_day": per_day,
            "interactions_per_day": per_day,
            "support_per_day": per_day,
        }
    )


def _ids():
    return {"orders": 0, "interactions": 0, "support-tickets": 0}


def test_zero_rates_produce_empty_lists_for_every_topic():
    events = sample_tick_events(_rates(per_day=0.0), 3600, START, _ids(), PRICES, np.random.default_rng(0))
    assert set(events) == set(TOPICS)
    assert all(v == [] for v in events.values())


def test_volume_tracks_rate_times_tick_length():
    # 50 customers * 5/day * 1 day tick = 250 expected per topic
    events = sample_tick_events(_rates(), 86400, START, _ids(), PRICES, np.random.default_rng(1))
    for topic in TOPICS:
        assert 180 < len(events[topic]) < 320


def test_ids_are_sequential_formatted_and_continue_from_next_ids():
    next_ids = {"orders": 100, "interactions": 7, "support-tickets": 0}
    events = sample_tick_events(_rates(), 86400, START, next_ids, PRICES, np.random.default_rng(2))
    order_ids = [e["order_id"] for e in events["orders"]]
    assert order_ids[0] == "O00000101"
    assert order_ids == [f"O{n:08d}" for n in range(101, 101 + len(order_ids))]
    assert next_ids["orders"] == 100 + len(order_ids)
    assert events["interactions"][0]["interaction_id"] == "I00000008"
    assert events["support-tickets"][0]["ticket_id"] == "T0000001"


def test_events_are_json_serializable_and_timestamps_fall_inside_the_tick():
    events = sample_tick_events(_rates(), 3600, START, _ids(), PRICES, np.random.default_rng(3))
    json.dumps(events)
    end = START + pd.Timedelta(seconds=3600)
    for e in events["orders"]:
        assert START <= pd.Timestamp(e["order_date"]) <= end
    for e in events["interactions"]:
        assert START <= pd.Timestamp(e["event_time"]) <= end


def test_order_amount_is_consistent_with_price_quantity_and_discount():
    events = sample_tick_events(_rates(), 86400, START, _ids(), PRICES, np.random.default_rng(4))
    for e in events["orders"]:
        expected = round(PRICES[e["product_id"]] * e["quantity"] * (1 - e["discount"]), 2)
        assert e["amount"] == expected
        assert e["status"] in {"completed", "cancelled", "refunded"}


def test_same_seed_gives_same_events():
    a = sample_tick_events(_rates(), 3600, START, _ids(), PRICES, np.random.default_rng(9))
    b = sample_tick_events(_rates(), 3600, START, _ids(), PRICES, np.random.default_rng(9))
    assert a == b


def test_next_ids_from_frames_uses_max_existing_sequence_and_handles_empty():
    orders = pd.DataFrame({"order_id": ["O00000001", "O00001000"], "order_date": pd.to_datetime(["2026-01-01", "2026-06-30"])})
    interactions = pd.DataFrame({"interaction_id": ["I00000042"], "event_time": pd.to_datetime(["2026-06-29"])})
    support = pd.DataFrame({"ticket_id": [], "created_at": pd.to_datetime([])})
    assert next_ids_from_frames(orders, interactions, support) == {"orders": 1000, "interactions": 42, "support-tickets": 0}
    assert stream_start_time(orders, interactions, support) == pd.Timestamp("2026-06-30")


def test_sequence_from_id_parses_digits_after_prefix():
    from streaming.events import sequence_from_id

    assert sequence_from_id("O00000123") == 123
    assert sequence_from_id("T0000007") == 7


def test_merge_next_ids_takes_per_topic_max_with_missing_as_zero():
    from streaming.events import merge_next_ids

    merged = merge_next_ids({"orders": 10, "interactions": 5}, {"orders": 12, "support-tickets": 3})
    assert merged == {"orders": 12, "interactions": 5, "support-tickets": 3}


def test_timestamps_have_at_most_microsecond_precision_and_stay_in_tick():
    events = sample_tick_events(_rates(per_day=20.0), 3600, START, _ids(), PRICES, np.random.default_rng(3))
    stamps = [e[k] for e in events["orders"] for k in ("order_date",)]
    assert stamps
    for s in stamps:
        frac = s.split(".")[1] if "." in s else ""
        assert len(frac) <= 6
        assert START <= pd.Timestamp(s) <= START + pd.Timedelta(seconds=3600)
