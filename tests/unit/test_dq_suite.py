"""Data-quality suite for the synthetic dataset (guide section 6).

Covers schema/dtype validation, duplicate detection, referential
integrity, invalid amount/date checks, and missingness — the same
checks any real ingestion pipeline for this data would need before
it's safe to build features on top of.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data import config
from data.schemas import Customer, Interaction, Order, Product, SupportTicket

SCHEMA_SAMPLE_SIZE = 200


def _validate_rows(df: pd.DataFrame, model, sample_size: int = SCHEMA_SAMPLE_SIZE) -> None:
    sample = df.head(sample_size)
    for record in sample.to_dict(orient="records"):
        model.model_validate(record)


class TestSchemaConformance:
    def test_customers_match_schema(self, dataset):
        _validate_rows(dataset["customers"], Customer)

    def test_products_match_schema(self, dataset):
        _validate_rows(dataset["products"], Product)

    def test_orders_match_schema(self, dataset):
        _validate_rows(dataset["orders"], Order)

    def test_interactions_match_schema(self, dataset):
        _validate_rows(dataset["interactions"], Interaction)

    def test_support_match_schema(self, dataset):
        _validate_rows(dataset["support"], SupportTicket)


class TestPrimaryKeys:
    @pytest.mark.parametrize(
        "table, key",
        [
            ("customers", "customer_id"),
            ("products", "product_id"),
            ("orders", "order_id"),
            ("interactions", "interaction_id"),
            ("support", "ticket_id"),
        ],
    )
    def test_primary_key_is_unique_and_not_null(self, dataset, table, key):
        col = dataset[table][key]
        assert col.notna().all(), f"{table}.{key} has nulls"
        assert col.is_unique, f"{table}.{key} has duplicates"


class TestReferentialIntegrity:
    def test_orders_reference_known_customers(self, dataset):
        known = set(dataset["customers"]["customer_id"])
        assert set(dataset["orders"]["customer_id"]) <= known

    def test_orders_reference_known_products(self, dataset):
        known = set(dataset["products"]["product_id"])
        assert set(dataset["orders"]["product_id"]) <= known

    def test_interactions_reference_known_customers(self, dataset):
        known = set(dataset["customers"]["customer_id"])
        assert set(dataset["interactions"]["customer_id"]) <= known

    def test_support_reference_known_customers(self, dataset):
        known = set(dataset["customers"]["customer_id"])
        assert set(dataset["support"]["customer_id"]) <= known


class TestValueRanges:
    def test_order_amounts_are_non_negative(self, dataset):
        assert (dataset["orders"]["amount"] >= 0).all()

    def test_order_quantities_are_positive(self, dataset):
        assert (dataset["orders"]["quantity"] > 0).all()

    def test_discounts_are_within_unit_interval(self, dataset):
        discount = dataset["orders"]["discount"]
        assert discount.between(0, 1).all()

    def test_product_prices_are_positive(self, dataset):
        assert (dataset["products"]["price"] > 0).all()

    def test_order_status_is_known(self, dataset):
        assert set(dataset["orders"]["status"]) <= {"completed", "refunded", "cancelled"}


class TestDateIntegrity:
    def test_no_events_before_data_start(self, dataset):
        data_start = pd.Timestamp(config.DATA_START)
        assert (dataset["customers"]["signup_date"] >= data_start).all()

    def test_no_events_after_data_end(self, dataset):
        data_end = pd.Timestamp(config.DATA_END)
        assert (dataset["orders"]["order_date"] <= data_end).all()
        assert (dataset["interactions"]["event_time"] <= data_end).all()
        assert (dataset["support"]["created_at"] <= data_end).all()

    def test_orders_never_precede_signup(self, dataset):
        orders = dataset["orders"].merge(
            dataset["customers"][["customer_id", "signup_date"]], on="customer_id"
        )
        assert (orders["order_date"] >= orders["signup_date"]).all()

    def test_interactions_never_precede_signup(self, dataset):
        interactions = dataset["interactions"].merge(
            dataset["customers"][["customer_id", "signup_date"]], on="customer_id"
        )
        assert (interactions["event_time"] >= interactions["signup_date"]).all()


class TestMissingness:
    @pytest.mark.parametrize("table", ["customers", "products", "orders", "interactions", "support"])
    def test_no_fully_null_columns(self, dataset, table):
        df = dataset[table]
        assert not df.isna().all().any(), f"{table} has a fully-null column"

    def test_required_customer_fields_have_no_nulls(self, dataset):
        required = ["customer_id", "signup_date", "country", "acquisition_channel", "plan"]
        assert not dataset["customers"][required].isna().any().any()
