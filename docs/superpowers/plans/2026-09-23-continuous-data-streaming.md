# Continuous Data Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep new orders, interactions, and support tickets arriving for existing customers via Kafka, loaded into Postgres by a real Spark Structured Streaming job.

**Architecture:** A host-run producer estimates per-customer rates from observable history, Poisson-samples events on a simulated clock, and publishes JSON to Kafka. A Spark cluster (master + worker + a `spark-submit` client container) reads the topics and upserts into Postgres with `ON CONFLICT DO NOTHING`. The batch job `build_backend_data.py` stops wiping tables and reads its inputs from Postgres.

**Tech Stack:** Python 3.11+, pandas/numpy, SQLAlchemy, kafka-python, PySpark 3.5 (inside Docker only), Kafka 3.7 (KRaft), Postgres 16, docker compose.

**Spec:** `docs/superpowers/specs/2026-09-22-continuous-data-streaming-design.md` (Task 7 amends it with the corrections listed below).

## Corrections to the spec (found while reading the code)

| Spec says | Reality / decision |
|---|---|
| `ON CONFLICT (id)`; table `support_tickets` | PKs are `order_id`, `interaction_id`, `ticket_id`; the support table is named `support`. Topic stays `support-tickets`, table is `support`. |
| `sample_tick_events(rates, tick_seconds, next_ids, rng)` | Also needs `tick_start` (simulated clock) and `product_prices` (for `amount`). |
| Events implicitly timestamped "now" | History ends at `DATA_END` = 2026-06-30. Wall-clock timestamps would leave a fake Jul–Sep 2026 dead gap. The producer runs a **simulated clock** starting at the latest timestamp in Postgres, advancing `tick_seconds * speed` per tick (default speed 3600). |
| Rate = count / tenure for everyone | That resurrects churned customers (their diluted rate stays nonzero). Customers with no order/interaction in the last 90 days before `as_of` get only the floor rate. |
| `build_backend_data.py` "unchanged logic" | It trains from parquet DataFrames, so streamed rows would be ignored. It must read its tables from Postgres (`read_raw_tables`). |
| `bitnami/spark:3.5` | Replaced by `apache/spark:3.5.1-python3` (official image). I believe Bitnami's free Docker Hub tags were withdrawn in 2025; verify at execution time and keep whichever pulls. |
| `toPandas()` in `foreachBatch` | `collect()` to plain tuples — numpy scalar types from pandas are not adapted by psycopg2, and it drops a pandas dependency in the Spark image. |
| Topic auto-creation | Added a `kafka-init` one-shot service to create topics before Spark subscribes. |

## Global Constraints

- Run Python via `.venv/Scripts/python.exe` from the repo root (`pytest` config: `testpaths = ["tests"]`, `src/` on path via `conftest.py`).
- Python `>=3.11`; new optional extra in `pyproject.toml`: `streaming = ["kafka-python>=2.0.3"]`.
- No exactly-once delivery: at-least-once + `INSERT ... ON CONFLICT (<pk>) DO NOTHING`.
- No new customers, no churn simulation, no streaming feature engineering; `data/generator.py` is not modified.
- All streaming services live under the compose profile `streaming`; `docker compose up -d postgres` must behave exactly as before.
- Kafka: KRaft single broker, internal listener `kafka:9092`, host listener `localhost:29092`. Topics: `orders`, `interactions`, `support-tickets`.
- Postgres from the host: port `5439`; from containers: `postgres:5432`.
- **Commit rule (project `CLAUDE.md`):** the agent never runs `git add`/`git commit`. Each "Commit" step means: output the commit block as text under the right heading (`Backend` for everything here except the root `README.md` and `docs/architecture.md`, which are `General`) and let the user run it. Never add `Co-Authored-By` or any Claude/Anthropic attribution.

## Review Focus

Failure modes the spec implies but never states, most likely first — each has a pinning test in the task named:

1. **Churned customers must not restart ordering.** A customer with no activity in the 90 days before `as_of` gets only the floor rate. (Task 1)
2. **Producer restart must not reuse IDs.** IDs continue from the max in Postgres; a fresh restart after 1,000 streamed rows must produce `O` numbers above the existing max. (Task 2)
3. **A tick with zero sampled events must produce empty lists, not errors**, and all-zero rates must not divide by zero. (Task 2)
4. **Producer JSON keys must equal the Postgres column names**, or Spark inserts NULLs / fails every batch. A contract test compares event keys with `Model.__table__` columns. (Task 5)
5. **Re-running `build_backend_data.py` must not delete streamed rows**, and its inputs must include them. (Task 3)

Known limitation (documented, not fixed here): `build_backend_data.py` scores at the fixed `OBSERVATION_CUTOFF` (2025-12-31), and streamed events are dated after `DATA_END` (2026-06-30). Point-in-time features therefore ignore them; the drift report will not change from streaming alone. Making the scoring cutoff advance with the data is a separate design decision (see Task 7 note).

## File Structure

| File | Responsibility |
|---|---|
| `src/streaming/__init__.py` | package marker |
| `src/streaming/rate_estimation.py` | `estimate_customer_rates` — pure, from observable history |
| `src/streaming/events.py` | `sample_tick_events`, `next_ids_from_frames`, `stream_start_time` — pure |
| `src/api/build_data.py` (modify) | add `raw_tables_seeded`, `read_raw_tables` |
| `scripts/build_backend_data.py` (modify) | seed once, read from Postgres |
| `scripts/stream_producer.py` | host entrypoint: state from Postgres, tick loop, Kafka publish |
| `spark/upsert_sql.py` | table specs (topic, table, pk, columns+types) and `build_upsert_sql` — no pyspark import so it is unit-testable |
| `spark/stream_ingest_job.py` | PySpark job: one stream per topic → `foreachBatch` upsert |
| `spark/Dockerfile` | spark-submit client image |
| `docker-compose.yml` (modify) | kafka, kafka-init, spark-master, spark-worker, spark-submit under `streaming` |
| `pyproject.toml`, `.env.example` (modify) | extra + Kafka variable |
| `docs/streaming.md` | runbook |
| `tests/unit/test_stream_rates.py`, `test_stream_events.py`, `test_stream_contract.py`, `tests/integration/test_build_data_seed.py` | tests |

---

### Task 1: Per-customer rate estimation

**Files:**
- Create: `src/streaming/__init__.py` (empty)
- Create: `src/streaming/rate_estimation.py`
- Test: `tests/unit/test_stream_rates.py`

**Interfaces:**
- Consumes: DataFrames shaped like the raw tables (`customers[customer_id, signup_date]`, `orders[customer_id, order_date]`, `interactions[customer_id, event_time]`, `support[customer_id, created_at]`).
- Produces: `estimate_customer_rates(customers, orders, interactions, support, as_of, dormant_days=90) -> pd.DataFrame` with columns `customer_id, orders_per_day, interactions_per_day, support_per_day`; constant `RATE_FLOOR_PER_DAY = 0.001`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_stream_rates.py
import pandas as pd
import pytest

from streaming.rate_estimation import RATE_FLOOR_PER_DAY, estimate_customer_rates

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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_stream_rates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'streaming'`

- [ ] **Step 3: Write the implementation**

```python
# src/streaming/rate_estimation.py
"""Per-customer event rates estimated from *observable* history only.

Deliberately does not use generator.py's hidden base_activity_rate (dropped
by to_public_customers): a real ingestion system would only know what is
in the tables. Customers with no order/interaction in the last
`dormant_days` before `as_of` are treated as churned and get only the
floor rate, so streaming does not resurrect them.
"""

from __future__ import annotations

import pandas as pd

RATE_FLOOR_PER_DAY = 0.001

_RATE_SOURCES = (
    ("orders_per_day", "orders"),
    ("interactions_per_day", "interactions"),
    ("support_per_day", "support"),
)


def estimate_customer_rates(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
    as_of,
    dormant_days: int = 90,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    frames = {"orders": orders, "interactions": interactions, "support": support}
    out = customers[["customer_id", "signup_date"]].reset_index(drop=True)
    tenure_days = (as_of - pd.to_datetime(out["signup_date"])).dt.days.clip(lower=1)

    last_activity = pd.concat(
        [
            orders.groupby("customer_id")["order_date"].max(),
            interactions.groupby("customer_id")["event_time"].max(),
        ]
    ).groupby(level=0).max()
    last_seen = out["customer_id"].map(last_activity)
    dormant = last_seen.isna() | (last_seen < as_of - pd.Timedelta(days=dormant_days))

    for column, key in _RATE_SOURCES:
        counts = out["customer_id"].map(frames[key].groupby("customer_id").size()).fillna(0)
        rate = (counts / tenure_days).clip(lower=RATE_FLOOR_PER_DAY)
        out[column] = rate.where(~dormant, RATE_FLOOR_PER_DAY)

    return out[["customer_id", "orders_per_day", "interactions_per_day", "support_per_day"]]
```

Also create the empty `src/streaming/__init__.py`.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_stream_rates.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit** (give as text, do not run)

Backend:
```
git add src/streaming/__init__.py src/streaming/rate_estimation.py tests/unit/test_stream_rates.py
git commit -m "feat(streaming): estimate per-customer event rates from observable history so streamed activity mirrors each customer's past behavior without resurrecting churned ones"
```

---

### Task 2: Tick event sampling and ID/clock seeding

**Files:**
- Create: `src/streaming/events.py`
- Test: `tests/unit/test_stream_events.py`

**Interfaces:**
- Consumes: the `rates` DataFrame from Task 1.
- Produces:
  - `TOPICS = ("orders", "interactions", "support-tickets")`
  - `sample_tick_events(rates, tick_seconds, tick_start, next_ids, product_prices, rng) -> dict[str, list[dict]]` — `tick_seconds` is **simulated** seconds; `tick_start` a `pd.Timestamp`; `next_ids` a `dict[str, int]` keyed by topic holding the last-used sequence number (mutated in place); `product_prices` a `dict[str, float]`; `rng` a `np.random.Generator`. Keys of the returned dict are `TOPICS`. Event dicts are JSON-serializable; timestamps are ISO strings.
  - `next_ids_from_frames(orders, interactions, support) -> dict[str, int]`
  - `stream_start_time(orders, interactions, support) -> pd.Timestamp`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_stream_events.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_stream_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'streaming.events'`

- [ ] **Step 3: Write the implementation**

```python
# src/streaming/events.py
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
    return (tick_start + pd.Timedelta(seconds=float(rng.uniform(0, tick_seconds)))).isoformat()


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


def _max_sequence(ids: pd.Series) -> int:
    return int(ids.str[1:].astype(int).max()) if len(ids) else 0


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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_stream_events.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit** (give as text, do not run)

Backend:
```
git add src/streaming/events.py tests/unit/test_stream_events.py
git commit -m "feat(streaming): sample per-tick events on a simulated clock with restart-safe IDs so a demo shows continuous activity without duplicate keys"
```

---

### Task 3: Seed-once build script that reads from Postgres

**Files:**
- Modify: `src/api/build_data.py` (add two functions after `load_raw_tables`, around line 61)
- Modify: `scripts/build_backend_data.py:108-123`
- Test: `tests/integration/test_build_data_seed.py`

**Interfaces:**
- Consumes: `api.models`, `load_raw_tables` (unchanged).
- Produces: `raw_tables_seeded(db: Session) -> bool`; `read_raw_tables(db: Session) -> dict[str, pd.DataFrame]` with keys `customers, products, orders, interactions, support`, where `customers.signup_date`, `orders.order_date`, `interactions.event_time`, `support.created_at` are `datetime64[ns]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_build_data_seed.py
"""The streaming design needs build_backend_data.py to stop wiping raw
tables (which would destroy rows Kafka/Spark loaded) and to read its
inputs from the database instead of the parquet seed files."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import models as db_models
from api.build_data import load_raw_tables, raw_tables_seeded, read_raw_tables
from api.database import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _load(db, dataset):
    load_raw_tables(db, dataset["customers"], dataset["products"], dataset["orders"], dataset["interactions"], dataset["support"])


def test_empty_database_is_not_seeded_and_loaded_one_is(session, dataset):
    assert raw_tables_seeded(session) is False
    _load(session, dataset)
    assert raw_tables_seeded(session) is True


def test_read_raw_tables_round_trips_counts_and_datetime_dtypes(session, dataset):
    _load(session, dataset)
    tables = read_raw_tables(session)
    assert set(tables) == {"customers", "products", "orders", "interactions", "support"}
    assert len(tables["orders"]) == len(dataset["orders"])
    assert len(tables["support"]) == len(dataset["support"])
    assert pd.api.types.is_datetime64_any_dtype(tables["customers"]["signup_date"])
    assert pd.api.types.is_datetime64_any_dtype(tables["orders"]["order_date"])
    assert pd.api.types.is_datetime64_any_dtype(tables["interactions"]["event_time"])
    assert pd.api.types.is_datetime64_any_dtype(tables["support"]["created_at"])


def test_streamed_rows_appear_in_read_raw_tables(session, dataset):
    _load(session, dataset)
    customer_id = dataset["customers"]["customer_id"].iloc[0]
    product_id = dataset["products"]["product_id"].iloc[0]
    session.add(
        db_models.Order(
            order_id="O99999999",
            customer_id=customer_id,
            order_date=pd.Timestamp("2026-07-15 10:00:00").to_pydatetime(),
            product_id=product_id,
            quantity=1,
            amount=9.99,
            discount=0.0,
            status="completed",
        )
    )
    session.commit()
    orders = read_raw_tables(session)["orders"]
    assert "O99999999" in set(orders["order_id"])
    assert len(orders) == len(dataset["orders"]) + 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_build_data_seed.py -v`
Expected: FAIL — `ImportError: cannot import name 'raw_tables_seeded'`

- [ ] **Step 3: Implement the two functions**

In `src/api/build_data.py`, add `from sqlalchemy import select` to the imports, then insert after `load_raw_tables`:

```python
def raw_tables_seeded(db: Session) -> bool:
    """True once `customers` has any row. build_backend_data.py uses this to
    seed from parquet exactly once instead of wiping rows Kafka/Spark streamed in."""
    return db.query(db_models.Customer).first() is not None


def read_raw_tables(db: Session) -> dict[str, pd.DataFrame]:
    """Current contents of the raw tables (seed history plus anything streamed
    in since) as the DataFrames the feature pipeline expects."""
    bind = db.get_bind()
    tables = {
        "customers": pd.read_sql(select(db_models.Customer), bind),
        "products": pd.read_sql(select(db_models.Product), bind),
        "orders": pd.read_sql(select(db_models.Order), bind),
        "interactions": pd.read_sql(select(db_models.Interaction), bind),
        "support": pd.read_sql(select(db_models.SupportTicket), bind),
    }
    tables["customers"]["signup_date"] = pd.to_datetime(tables["customers"]["signup_date"])
    tables["orders"]["order_date"] = pd.to_datetime(tables["orders"]["order_date"])
    tables["interactions"]["event_time"] = pd.to_datetime(tables["interactions"]["event_time"])
    tables["support"]["created_at"] = pd.to_datetime(tables["support"]["created_at"])
    return tables
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_build_data_seed.py tests/integration/test_build_data_reload.py -v`
Expected: all passed

- [ ] **Step 5: Change the build script**

In `scripts/build_backend_data.py`, change the import block to add `raw_tables_seeded, read_raw_tables`, and replace the block from `raw = ROOT / "data" / "raw"` through `load_raw_tables(...)` (lines 110-123) with:

```python
    test_cutoff = pd.Timestamp(config.OBSERVATION_CUTOFF)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if raw_tables_seeded(db):
            print("raw tables already seeded -- keeping existing (and any streamed) rows")
        else:
            print("seeding raw tables from data/raw/*.parquet...")
            raw = ROOT / "data" / "raw"
            load_raw_tables(
                db,
                pd.read_parquet(raw / "customers.parquet"),
                pd.read_parquet(raw / "products.parquet"),
                pd.read_parquet(raw / "orders.parquet"),
                pd.read_parquet(raw / "interactions.parquet"),
                pd.read_parquet(raw / "support.parquet"),
            )
        tables = read_raw_tables(db)
        customers, products = tables["customers"], tables["products"]
        orders, interactions, support = tables["orders"], tables["interactions"], tables["support"]
```

Keep `MODELS_DIR.mkdir(exist_ok=True)` as the first line of `main()`. Update the module docstring's first sentence to: "One-shot batch job: seed raw data once, then train/persist ... from whatever the raw tables currently hold."

- [ ] **Step 6: Verify the script still works end to end**

Run (Postgres already seeded from earlier runs): `docker compose up -d postgres` then `.venv/Scripts/python.exe scripts/build_backend_data.py`
Expected: prints `raw tables already seeded -- keeping ...`, then trains and prints `churn PR-AUC: 0.735` (same headline number as before) and `done.`. If PR-AUC differs materially, stop and investigate before continuing — reading from Postgres must be equivalent to reading parquet.

Then run the full suite: `.venv/Scripts/python.exe -m pytest -q` — Expected: all pass (108 existing + new).

- [ ] **Step 7: Commit** (give as text, do not run)

Backend:
```
git add src/api/build_data.py scripts/build_backend_data.py tests/integration/test_build_data_seed.py
git commit -m "feat(build): seed raw tables once and read pipeline inputs from Postgres so streamed rows are kept and included instead of wiped on every run"
```

---

### Task 4: Producer entrypoint and dependency wiring

**Files:**
- Create: `scripts/stream_producer.py`
- Modify: `pyproject.toml` (add extra), `.env.example` (add variable)

**Interfaces:**
- Consumes: `read_raw_tables` (Task 3), `estimate_customer_rates` (Task 1), `sample_tick_events`, `next_ids_from_frames`, `stream_start_time`, `TOPICS` (Task 2), `SessionLocal` from `api.database`.
- Produces: a CLI, `python scripts/stream_producer.py [--tick-seconds 5] [--speed 3600] [--bootstrap localhost:29092] [--seed 7]`. Publishes each event as JSON with key = `customer_id` to the topic of the same name.

- [ ] **Step 1: Add the extra and env var**

`pyproject.toml`, after the `mlops` block:

```toml
streaming = [
    "kafka-python>=2.0.3",
]
```

`.env.example`, append:

```
# Streaming (optional; see docs/streaming.md). Host-side address of the Kafka
# container's external listener.
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
```

- [ ] **Step 2: Write the producer**

```python
# scripts/stream_producer.py
"""Continuously publish simulated customer activity to Kafka.

Runs on the host (like scripts/generate_data.py). On startup it reads the
current tables from Postgres, estimates per-customer rates, resumes the ID
counters and the simulated clock from what is already stored, then every
`--tick-seconds` of real time samples `tick_seconds * speed` simulated
seconds of activity and publishes it.

Usage:
    docker compose --profile streaming up -d
    .venv/Scripts/python.exe scripts/stream_producer.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api.build_data import raw_tables_seeded, read_raw_tables  # noqa: E402
from api.database import SessionLocal  # noqa: E402
from streaming.events import next_ids_from_frames, sample_tick_events, stream_start_time  # noqa: E402
from streaming.rate_estimation import estimate_customer_rates  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tick-seconds", type=float, default=5.0, help="real seconds between ticks")
    parser.add_argument("--speed", type=float, default=3600.0, help="simulated seconds per real second (3600 = 1 sim hour/sec)")
    parser.add_argument("--bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"))
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        from kafka import KafkaProducer
    except ImportError:
        sys.exit("kafka-python is not installed: pip install -e '.[streaming]'")

    db = SessionLocal()
    try:
        if not raw_tables_seeded(db):
            sys.exit("customers table is empty -- run scripts/build_backend_data.py first to seed it")
        tables = read_raw_tables(db)
    finally:
        db.close()

    customers, products = tables["customers"], tables["products"]
    orders, interactions, support = tables["orders"], tables["interactions"], tables["support"]

    sim_clock = stream_start_time(orders, interactions, support)
    rates = estimate_customer_rates(customers, orders, interactions, support, as_of=sim_clock)
    next_ids = next_ids_from_frames(orders, interactions, support)
    product_prices = dict(zip(products["product_id"], products["price"].astype(float)))
    rng = np.random.default_rng(args.seed)

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    sim_seconds_per_tick = args.tick_seconds * args.speed
    print(
        f"streaming to {args.bootstrap}: {len(rates)} customers, simulated clock starts {sim_clock}, "
        f"{sim_seconds_per_tick / 3600:.1f} simulated hours per {args.tick_seconds:g}s tick. Ctrl+C to stop."
    )

    try:
        while True:
            time.sleep(args.tick_seconds)
            events = sample_tick_events(rates, sim_seconds_per_tick, sim_clock, next_ids, product_prices, rng)
            for topic, messages in events.items():
                for message in messages:
                    producer.send(topic, key=message["customer_id"], value=message)
            producer.flush()
            sim_clock += pd.Timedelta(seconds=sim_seconds_per_tick)
            counts = ", ".join(f"{topic}={len(messages)}" for topic, messages in events.items())
            print(f"[sim {sim_clock:%Y-%m-%d %H:%M}] published {counts}")
    except KeyboardInterrupt:
        print("stopping")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-check without Kafka**

Run: `.venv/Scripts/python.exe scripts/stream_producer.py --help`
Expected: usage text listing `--tick-seconds`, `--speed`, `--bootstrap`, `--seed`, exit 0 (no Kafka needed; the import of `kafka` happens after arg parsing).

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit** (give as text, do not run)

Backend:
```
git add scripts/stream_producer.py pyproject.toml .env.example
git commit -m "feat(streaming): add host-side Kafka producer with restart-safe IDs and a simulated clock so activity continues from where history ends"
```

---

### Task 5: Spark ingestion job with a tested contract

**Files:**
- Create: `spark/upsert_sql.py`, `spark/stream_ingest_job.py`, `spark/Dockerfile`
- Test: `tests/unit/test_stream_contract.py`

**Interfaces:**
- Consumes: event dicts from Task 2; Postgres tables via `api.models` (tests only).
- Produces: `spark/upsert_sql.py` exposing `TableSpec` (frozen dataclass: `topic, table, pk, columns: tuple[tuple[str, str], ...]` of `(name, spark_sql_type)`; properties `column_names`, `ddl`) and `TABLES: dict[str, TableSpec]` keyed by topic, and `build_upsert_sql(table, columns, pk) -> str`.

- [ ] **Step 1: Write the failing contract test**

```python
# tests/unit/test_stream_contract.py
"""The producer's JSON keys, the Spark job's column lists, and the ORM
tables must agree exactly. A mismatch would not fail loudly: Spark would
insert NULLs or crash-loop inside a container, far from any test."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "spark"))

from upsert_sql import TABLES, build_upsert_sql  # noqa: E402

from api import models as db_models  # noqa: E402
from streaming.events import TOPICS, sample_tick_events  # noqa: E402

_MODEL_FOR_TOPIC = {
    "orders": db_models.Order,
    "interactions": db_models.Interaction,
    "support-tickets": db_models.SupportTicket,
}


def test_spark_specs_cover_exactly_the_producer_topics():
    assert set(TABLES) == set(TOPICS)


def test_spark_columns_match_orm_table_columns():
    for topic, spec in TABLES.items():
        model = _MODEL_FOR_TOPIC[topic]
        assert spec.table == model.__tablename__
        assert set(spec.column_names) == set(model.__table__.columns.keys())
        assert spec.pk in model.__table__.primary_key.columns.keys()


def test_producer_event_keys_match_spark_columns():
    rates = pd.DataFrame(
        {"customer_id": ["C000001"] * 5, "orders_per_day": 50.0, "interactions_per_day": 50.0, "support_per_day": 50.0}
    )
    events = sample_tick_events(
        rates, 86400, pd.Timestamp("2026-06-30"), {t: 0 for t in TOPICS}, {"P00001": 10.0}, np.random.default_rng(0)
    )
    for topic, spec in TABLES.items():
        assert events[topic], f"no {topic} events sampled"
        for event in events[topic]:
            assert set(event) == set(spec.column_names)


def test_upsert_sql_is_idempotent_on_the_primary_key():
    sql = build_upsert_sql("orders", ["order_id", "customer_id"], "order_id")
    assert sql == "INSERT INTO orders (order_id, customer_id) VALUES %s ON CONFLICT (order_id) DO NOTHING"


def test_ddl_lists_every_column_with_its_type():
    ddl = TABLES["orders"].ddl
    assert "order_id STRING" in ddl and "amount DOUBLE" in ddl and "quantity INT" in ddl
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_stream_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'upsert_sql'`

- [ ] **Step 3: Write `spark/upsert_sql.py`**

```python
"""Table specs and SQL for the Spark ingest job. Deliberately free of any
pyspark import so tests/unit/test_stream_contract.py can import it and
check it against the ORM models and the producer's event shape."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    topic: str
    table: str
    pk: str
    columns: tuple[tuple[str, str], ...]  # (column name, Spark SQL type)

    @property
    def column_names(self) -> list[str]:
        return [name for name, _ in self.columns]

    @property
    def ddl(self) -> str:
        return ", ".join(f"{name} {sql_type}" for name, sql_type in self.columns)


# Timestamps stay STRING in Spark (ISO-8601); Postgres casts the literal on insert.
TABLES: dict[str, TableSpec] = {
    "orders": TableSpec(
        topic="orders",
        table="orders",
        pk="order_id",
        columns=(
            ("order_id", "STRING"),
            ("customer_id", "STRING"),
            ("order_date", "STRING"),
            ("product_id", "STRING"),
            ("quantity", "INT"),
            ("amount", "DOUBLE"),
            ("discount", "DOUBLE"),
            ("status", "STRING"),
        ),
    ),
    "interactions": TableSpec(
        topic="interactions",
        table="interactions",
        pk="interaction_id",
        columns=(
            ("interaction_id", "STRING"),
            ("customer_id", "STRING"),
            ("event_time", "STRING"),
            ("event_type", "STRING"),
            ("channel", "STRING"),
        ),
    ),
    "support-tickets": TableSpec(
        topic="support-tickets",
        table="support",
        pk="ticket_id",
        columns=(
            ("ticket_id", "STRING"),
            ("customer_id", "STRING"),
            ("created_at", "STRING"),
            ("category", "STRING"),
        ),
    ),
}


def build_upsert_sql(table: str, columns: list[str], pk: str) -> str:
    """Idempotent insert for psycopg2 execute_values: a redelivered Kafka
    message hits the primary key and is skipped instead of duplicated."""
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s ON CONFLICT ({pk}) DO NOTHING"
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_stream_contract.py -v`
Expected: 5 passed

- [ ] **Step 5: Write `spark/stream_ingest_job.py`**

```python
"""Structured Streaming job: Kafka topics -> Postgres raw tables.

One stream per topic. Each micro-batch is collected on the driver (volumes
here are small) and written with psycopg2 `INSERT ... ON CONFLICT DO
NOTHING`, so Spark's at-least-once redelivery after a crash cannot create
duplicate rows. Checkpoints live on a mounted volume so a restart resumes
from the last committed offset.
"""

from __future__ import annotations

import os

import psycopg2
from psycopg2.extras import execute_values
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json

from upsert_sql import TABLES, TableSpec, build_upsert_sql

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
CHECKPOINT_ROOT = os.environ.get("CHECKPOINT_ROOT", "/checkpoints")


def _connect():
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "postgres"),
        port=int(os.environ.get("PG_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "cip"),
        password=os.environ.get("POSTGRES_PASSWORD", "changeme"),
        dbname=os.environ.get("POSTGRES_DB", "customer_intelligence"),
    )


def _make_batch_writer(spec: TableSpec):
    columns = spec.column_names
    sql = build_upsert_sql(spec.table, columns, spec.pk)

    def write(batch_df, batch_id: int) -> None:
        rows = [tuple(row[c] for c in columns) for row in batch_df.select(*columns).collect()]
        if not rows:
            return
        conn = _connect()
        try:
            with conn, conn.cursor() as cur:
                execute_values(cur, sql, rows)
        finally:
            conn.close()
        print(f"[{spec.topic}] batch {batch_id}: upserted {len(rows)} rows into {spec.table}", flush=True)

    return write


def _start_stream(spark: SparkSession, spec: TableSpec):
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", spec.topic)
        .option("startingOffsets", "earliest")
        .load()
    )
    events = (
        raw.select(from_json(col("value").cast("string"), spec.ddl).alias("e"))
        .select("e.*")
        .where(col(spec.pk).isNotNull())  # drop malformed messages
    )
    return (
        events.writeStream.foreachBatch(_make_batch_writer(spec))
        .option("checkpointLocation", f"{CHECKPOINT_ROOT}/{spec.topic}")
        .trigger(processingTime="5 seconds")
        .start()
    )


def main() -> None:
    spark = SparkSession.builder.appName("cip-stream-ingest").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    for spec in TABLES.values():
        _start_stream(spark, spec)
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Write `spark/Dockerfile`** (build context is the repo root)

```dockerfile
# spark-submit client for the streaming profile. Same image family as the
# spark-master/spark-worker services so Python and Spark versions match.
FROM apache/spark:3.5.1-python3

USER root
RUN pip install --no-cache-dir psycopg2-binary
COPY spark/stream_ingest_job.py spark/upsert_sql.py /app/

# Runs as root so the mounted ivy-cache and checkpoint volumes are writable.
CMD ["/opt/spark/bin/spark-submit", \
     "--master", "spark://spark-master:7077", \
     "--conf", "spark.jars.ivy=/ivy", \
     "--conf", "spark.driver.host=spark-submit", \
     "--conf", "spark.driver.bindAddress=0.0.0.0", \
     "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.3", \
     "/app/stream_ingest_job.py"]
```

- [ ] **Step 7: Full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass. (`spark/stream_ingest_job.py` is not imported by tests — it needs pyspark, which only lives in the Docker image; Task 6 verifies it against the real stack.)

- [ ] **Step 8: Commit** (give as text, do not run)

Backend:
```
git add spark/upsert_sql.py spark/stream_ingest_job.py spark/Dockerfile tests/unit/test_stream_contract.py
git commit -m "feat(streaming): add Spark Structured Streaming job with idempotent Postgres upserts and a contract test tying event keys to table columns"
```

---

### Task 6: Compose services and end-to-end verification

**Files:**
- Modify: `docker-compose.yml` (add services under `streaming`, extend `volumes:`)

**Interfaces:**
- Consumes: `spark/Dockerfile` (Task 5), `postgres` service.
- Produces: `docker compose --profile streaming up -d` brings up `kafka`, `kafka-init`, `spark-master`, `spark-worker`, `spark-submit`.

- [ ] **Step 1: Add the services**

Insert before the top-level `volumes:` in `docker-compose.yml`:

```yaml
  # ---- Continuous data streaming (see docs/streaming.md) -------------------
  # Not started by a bare `docker compose up`; use `--profile streaming`.
  kafka:
    image: apache/kafka:3.7.0
    profiles: ["streaming"]
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: INTERNAL://:9092,EXTERNAL://:29092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: INTERNAL://kafka:9092,EXTERNAL://localhost:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: INTERNAL:PLAINTEXT,EXTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: INTERNAL
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
    ports:
      - "29092:29092"
    healthcheck:
      test: ["CMD-SHELL", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 > /dev/null 2>&1"]
      interval: 10s
      timeout: 10s
      retries: 12

  kafka-init:
    image: apache/kafka:3.7.0
    profiles: ["streaming"]
    depends_on:
      kafka:
        condition: service_healthy
    restart: "no"
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        for t in orders interactions support-tickets; do
          /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic $$t --partitions 1 --replication-factor 1
        done

  spark-master:
    image: apache/spark:3.5.1-python3
    profiles: ["streaming"]
    command: ["/opt/spark/bin/spark-class", "org.apache.spark.deploy.master.Master", "--host", "spark-master"]
    ports:
      - "8080:8080"

  spark-worker:
    image: apache/spark:3.5.1-python3
    profiles: ["streaming"]
    command: ["/opt/spark/bin/spark-class", "org.apache.spark.deploy.worker.Worker", "spark://spark-master:7077"]
    depends_on:
      - spark-master

  spark-submit:
    build:
      context: .
      dockerfile: spark/Dockerfile
    profiles: ["streaming"]
    user: root
    restart: unless-stopped
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      PG_HOST: postgres
      POSTGRES_USER: ${POSTGRES_USER:-cip}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      POSTGRES_DB: ${POSTGRES_DB:-customer_intelligence}
    volumes:
      - spark_checkpoints:/checkpoints
      - spark_ivy:/ivy
    depends_on:
      postgres:
        condition: service_healthy
      kafka-init:
        condition: service_completed_successfully
      spark-master:
        condition: service_started
      spark-worker:
        condition: service_started
```

Extend the bottom `volumes:` block:

```yaml
volumes:
  postgres_data:
  spark_checkpoints:
  spark_ivy:
```

- [ ] **Step 2: Validate the file**

Run: `docker compose --profile streaming config -q`
Expected: no output, exit 0.
Run: `docker compose config --services`
Expected: only `postgres` (streaming and api services stay hidden without their profiles).

- [ ] **Step 3: Bring up the stack**

Run: `docker compose up -d postgres` then `docker compose --profile streaming up -d --build`
Expected: all services start; `docker compose --profile streaming ps` shows `kafka` healthy, `kafka-init` exited 0, `spark-submit` running.
Run: `docker compose --profile streaming logs spark-submit --tail 40`
Expected: Maven `--packages` resolution on first run (a few minutes), then no Python traceback. If `apache/spark:3.5.1-python3` cannot be pulled or the master/worker commands fail, fix the image/command here rather than working around it in the job.

- [ ] **Step 4: Run the producer and watch rows climb**

```
.venv/Scripts/python.exe -m pip install -e ".[streaming]"
.venv/Scripts/python.exe scripts/stream_producer.py --seed 7
```
Expected: `streaming to localhost:29092: 8000 customers, simulated clock starts 2026-06-30 ...`, then one `published orders=..., interactions=..., support-tickets=...` line per tick.
In another terminal, run twice ~30s apart:
`docker compose exec postgres psql -U cip -d customer_intelligence -c "select count(*) from orders; select count(*) from interactions; select count(*) from support;"`
Expected: counts strictly increase; `select max(order_date) from orders` moves past `2026-06-30`.

- [ ] **Step 5: Verify idempotency, restart-safety, and the batch job**

1. Idempotency: `docker compose --profile streaming restart spark-submit`, then compare `select count(*), count(distinct order_id) from orders;` — both numbers equal (no duplicates after Spark replays from its checkpoint).
2. Producer restart: stop the producer with Ctrl+C, start it again, confirm no `duplicate key` errors in `docker compose --profile streaming logs spark-submit` and that new order IDs continue above the previous max.
3. Batch job: `.venv/Scripts/python.exe scripts/build_backend_data.py` — expected: prints `raw tables already seeded -- keeping ...` and finishes; then re-run the `count(*)` query and confirm the streamed rows are still there.

- [ ] **Step 6: Commit** (give as text, do not run)

Backend:
```
git add docker-compose.yml
git commit -m "feat(streaming): add Kafka and Spark cluster services under a streaming profile so continuous ingestion runs with one compose command"
```

---

### Task 7: Runbook, README pointer, and spec amendments

**Files:**
- Create: `docs/streaming.md`
- Modify: `README.md` (add a short pointer section), `docs/superpowers/specs/2026-09-22-continuous-data-streaming-design.md` (amend), `docs/architecture.md` (one bullet)

- [ ] **Step 1: Write `docs/streaming.md`**

Contents (write out fully, no placeholders): a title; the diagram from the spec; "Run it" with the three commands from Task 6 Steps 3–4 plus `docker compose --profile streaming down -v` to reset; "How it works" (rate estimation from observable history, dormant customers stay floor-rate, simulated clock and `--speed`, at-least-once + `ON CONFLICT DO NOTHING`); "Reset rule: remove Kafka and checkpoint volumes together — `down -v` — never one without the other, or Spark's checkpoint offsets will point past an empty topic"; and the "Known limitations" section: no new signups, no live churn, scoring cutoff stays at `OBSERVATION_CUTOFF` (2025-12-31) so streamed events dated after 2026-06-30 do not change model features or drift yet.

- [ ] **Step 2: Amend the spec**

In the spec, apply the corrections table from the top of this plan (PK names and `support` table name, extra `sample_tick_events` parameters, simulated clock, dormant rule, `read_raw_tables`, image choice, `collect()`, `kafka-init`).

- [ ] **Step 3: Add the README and architecture pointers**

`README.md`: read it, then add under the existing run/usage instructions a section:

```markdown
## Continuous data (optional)

New orders, interactions, and support tickets can stream in continuously
through Kafka and a Spark cluster into Postgres. See
[docs/streaming.md](docs/streaming.md).
```

`docs/architecture.md`: add one bullet under the repository layout for `src/streaming/`, `spark/`, and `scripts/stream_producer.py`, matching the file's existing style.

- [ ] **Step 4: Verify**

Run: `.venv/Scripts/python.exe -m pytest -q` — Expected: all pass.
Re-read `docs/streaming.md` once against the commands you actually ran in Task 6; fix any that differ.

- [ ] **Step 5: Commit** (give as text, do not run)

Backend (spec, streaming runbook):
```
git add docs/streaming.md docs/superpowers/specs/2026-09-22-continuous-data-streaming-design.md docs/superpowers/plans/2026-09-23-continuous-data-streaming.md
git commit -m "docs(streaming): add runbook and align the spec with what the code needed (real PK names, simulated clock, DB-backed batch job)"
```

General (root README and cross-cutting architecture doc; commit after the Backend groups):
```
git add README.md docs/architecture.md
git commit -m "docs: point the README and architecture doc at the new streaming layer"
```

---

## Self-review

- **Spec coverage:** rate estimation (T1), event sampling (T2), seed-once build script (T3), producer (T4), Spark job + Dockerfile (T5), compose profile (T6), `streaming` extra (T4), unit tests for pure modules (T1, T2, T5), manual real-stack verification (T6), rollout doc (T7). Delivery semantics covered by the `ON CONFLICT` SQL test plus the replay check in T6 Step 5.
- **Placeholders:** none in code steps. T7 Step 1 describes prose content because it is documentation, not code.
- **Type consistency:** `estimate_customer_rates` columns (`orders_per_day`, `interactions_per_day`, `support_per_day`) match `_RATE_COLUMN` in Task 2; `next_ids` keys equal `TOPICS`; `TableSpec.column_names` equals event dict keys (pinned by the contract test); `read_raw_tables` keys match those consumed in Tasks 3 and 4.
- **Open decision for the user:** scoring cutoff (see "Known limitation"). Options: (a) leave as documented; (b) add `--as-of` to the batch job so retraining can move past `OBSERVATION_CUTOFF` once enough streamed data exists. Recommend (a) first, revisit after the stream works.
