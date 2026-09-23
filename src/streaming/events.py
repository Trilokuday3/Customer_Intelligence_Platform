"""Pure event sampling for the streaming producer.

Distributions (order status, interaction types/channels, ticket
categories, discounts, ID formats) are copied from data/generator.py so
streamed activity looks like the same simulated business. Kept as pure
functions of (rates, clock, rng) so they are unit-testable without Kafka.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TOPICS = ("orders", "interactions", "support-tickets")

_RATE_COLUMN = {
    "orders": "orders_per_day",
    "interactions": "interactions_per_day",
    "support-tickets": "support_per_day",
}
_INTERACTION_TYPES = ["login", "page_view", "add_to_cart", "email_open", "email_click"]
_INTERACTION_TYPE_PROBS = [0.25, 0.4, 0.15, 0.15, 0.05]
_INTERACTION_CHANNELS = ["web", "mobile_app", "email"]
_INTERACTION_CHANNEL_PROBS = [0.55, 0.35, 0.10]
_TICKET_CATEGORIES = ["billing", "shipping", "product_issue", "cancellation_request", "general"]
_TICKET_CATEGORY_PROBS = [0.25, 0.25, 0.25, 0.1, 0.15]
_DISCOUNTS = [0.0, 0.0, 0.0, 0.1, 0.2]


def _timestamp(tick_start: pd.Timestamp, tick_seconds: float, rng: np.random.Generator) -> str:
    stamp = tick_start + pd.Timedelta(seconds=float(rng.uniform(0, tick_seconds)))
    return stamp.isoformat(timespec="microseconds")


def _next_id(next_ids: dict[str, int], topic: str, prefix: str, width: int) -> str:
    next_ids[topic] += 1
    return f"{prefix}{next_ids[topic]:0{width}d}"


def _order(customer_id, ts, next_ids, product_ids, product_prices, rng) -> dict:
    product_id = str(rng.choice(product_ids))
    quantity = int(rng.integers(1, 4))
    discount = float(rng.choice(_DISCOUNTS))
    roll = rng.random()
    status = "cancelled" if roll < 0.02 else "refunded" if roll < 0.06 else "completed"
    return {
        "order_id": _next_id(next_ids, "orders", "O", 8),
        "customer_id": customer_id,
        "order_date": ts,
        "product_id": product_id,
        "quantity": quantity,
        "amount": round(product_prices[product_id] * quantity * (1 - discount), 2),
        "discount": discount,
        "status": status,
    }


def _interaction(customer_id, ts, next_ids, rng) -> dict:
    return {
        "interaction_id": _next_id(next_ids, "interactions", "I", 8),
        "customer_id": customer_id,
        "event_time": ts,
        "event_type": str(rng.choice(_INTERACTION_TYPES, p=_INTERACTION_TYPE_PROBS)),
        "channel": str(rng.choice(_INTERACTION_CHANNELS, p=_INTERACTION_CHANNEL_PROBS)),
    }


def _ticket(customer_id, ts, next_ids, rng) -> dict:
    return {
        "ticket_id": _next_id(next_ids, "support-tickets", "T", 7),
        "customer_id": customer_id,
        "created_at": ts,
        "category": str(rng.choice(_TICKET_CATEGORIES, p=_TICKET_CATEGORY_PROBS)),
    }


def sample_tick_events(
    rates: pd.DataFrame,
    tick_seconds: float,
    tick_start: pd.Timestamp,
    next_ids: dict[str, int],
    product_prices: dict[str, float],
    rng: np.random.Generator,
) -> dict[str, list[dict]]:
    """Poisson-sample this tick's events. `tick_seconds` is simulated time.
    Mutates `next_ids` (last-used sequence number per topic)."""
    customer_ids = rates["customer_id"].to_numpy()
    product_ids = np.array(list(product_prices))
    events: dict[str, list[dict]] = {topic: [] for topic in TOPICS}

    for topic in TOPICS:
        lam = rates[_RATE_COLUMN[topic]].to_numpy(dtype=float) * tick_seconds / 86400.0
        counts = rng.poisson(lam)
        for idx in np.flatnonzero(counts):
            customer_id = str(customer_ids[idx])
            for _ in range(int(counts[idx])):
                ts = _timestamp(tick_start, tick_seconds, rng)
                if topic == "orders":
                    events[topic].append(_order(customer_id, ts, next_ids, product_ids, product_prices, rng))
                elif topic == "interactions":
                    events[topic].append(_interaction(customer_id, ts, next_ids, rng))
                else:
                    events[topic].append(_ticket(customer_id, ts, next_ids, rng))
    return events


def sequence_from_id(event_id: str) -> int:
    """Numeric part of an ID such as "O00000123" (one-letter prefix + digits)."""
    return int(event_id[1:])


def _max_sequence(ids: pd.Series) -> int:
    return int(ids.map(sequence_from_id).max()) if len(ids) else 0


def merge_next_ids(db_ids: dict[str, int], kafka_ids: dict[str, int]) -> dict[str, int]:
    """Per-topic max of the database and last-Kafka-message sequences (missing = 0)."""
    return {topic: max(db_ids.get(topic, 0), kafka_ids.get(topic, 0)) for topic in TOPICS}


def next_ids_from_frames(orders: pd.DataFrame, interactions: pd.DataFrame, support: pd.DataFrame) -> dict[str, int]:
    """Last-used sequence number per topic, so a restarted producer never reuses an ID."""
    return {
        "orders": _max_sequence(orders["order_id"]),
        "interactions": _max_sequence(interactions["interaction_id"]),
        "support-tickets": _max_sequence(support["ticket_id"]),
    }


def stream_start_time(orders: pd.DataFrame, interactions: pd.DataFrame, support: pd.DataFrame) -> pd.Timestamp:
    """Where the simulated clock resumes: the latest event already in the database."""
    candidates = [
        orders["order_date"].max(),
        interactions["event_time"].max(),
        support["created_at"].max(),
    ]
    return max(pd.Timestamp(c) for c in candidates if pd.notna(c))
