"""Regression test for a real bug: load_raw_tables() used to delete
`customers` before the tables that foreign-key to it (predictions,
customer_segments, customer_explanations), which SQLite's default
(no FK enforcement) never catches but a real Postgres run does --
build_backend_data.py crashed on its *second* run against a
persistent Postgres database with `ForeignKeyViolation`. This test
turns FK enforcement on for a throwaway SQLite engine specifically so
the bug is caught here instead of only in production.
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.build_data import load_raw_tables, store_predictions, store_segments
from api.database import Base
from data import config


@pytest.fixture
def fk_enforced_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestLoadRawTablesReload:
    def test_second_load_does_not_violate_foreign_keys(self, fk_enforced_session, dataset):
        db = fk_enforced_session
        customers, products, orders, interactions, support = (
            dataset["customers"],
            dataset["products"],
            dataset["orders"],
            dataset["interactions"],
            dataset["support"],
        )

        load_raw_tables(db, customers, products, orders, interactions, support)
        store_predictions(
            db,
            customers["customer_id"],
            [0.5] * len(customers),
            [100.0] * len(customers),
            "test-v1",
            pd.Timestamp(config.OBSERVATION_CUTOFF).date(),
        )
        store_segments(db, customers["customer_id"], ["Champions"] * len(customers), pd.Timestamp(config.OBSERVATION_CUTOFF).date())

        # This is the call that used to raise IntegrityError against a real
        # foreign-key-enforcing database once predictions/segments existed.
        load_raw_tables(db, customers, products, orders, interactions, support)
