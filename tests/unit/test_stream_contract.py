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
