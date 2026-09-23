"""The streaming design needs build_backend_data.py to stop wiping raw
tables (which would destroy rows Kafka/Spark loaded) and to read its
inputs from the database instead of the parquet seed files."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import models as db_models
from api.build_data import load_raw_tables, raw_tables_seeded, read_raw_tables, seed_raw_tables_if_empty
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


def _frames(dataset):
    return tuple(dataset[k] for k in ("customers", "products", "orders", "interactions", "support"))


def test_seed_if_empty_seeds_an_empty_database(session, dataset):
    assert seed_raw_tables_if_empty(session, lambda: _frames(dataset)) is True
    assert raw_tables_seeded(session) is True
    assert len(read_raw_tables(session)["orders"]) == len(dataset["orders"])


def test_seed_if_empty_keeps_streamed_rows_on_rerun(session, dataset):
    assert seed_raw_tables_if_empty(session, lambda: _frames(dataset)) is True
    session.add(
        db_models.Order(
            order_id="O99999999",
            customer_id=dataset["customers"]["customer_id"].iloc[0],
            order_date=pd.Timestamp("2026-07-15 10:00:00").to_pydatetime(),
            product_id=dataset["products"]["product_id"].iloc[0],
            quantity=1,
            amount=9.99,
            discount=0.0,
            status="completed",
        )
    )
    session.commit()

    def _must_not_be_called():
        raise AssertionError("load_frames called on an already-seeded database")

    assert seed_raw_tables_if_empty(session, _must_not_be_called) is False
    orders = read_raw_tables(session)["orders"]
    assert "O99999999" in set(orders["order_id"])
    assert len(orders) == len(dataset["orders"]) + 1
