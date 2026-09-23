"""Populates the API's database: raw tables, batch predictions, segment
assignments, model-run metrics, and precomputed local explanations.

Called by scripts/build_backend_data.py against the real generated
dataset, and directly by tests/integration/test_api.py against a temp
SQLite DB and tiny models trained on the small fixture dataset — same
code path, different scale, so a bug here fails fast in tests rather
than only showing up against the full dataset.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import models as db_models
from explainability.shap_utils import local_explanation


def load_raw_tables(
    db: Session,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    orders: pd.DataFrame,
    interactions: pd.DataFrame,
    support: pd.DataFrame,
) -> None:
    customers = customers.copy()
    customers["signup_date"] = pd.to_datetime(customers["signup_date"]).dt.date
    orders = orders.copy()
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    interactions = interactions.copy()
    interactions["event_time"] = pd.to_datetime(interactions["event_time"])
    support = support.copy()
    support["created_at"] = pd.to_datetime(support["created_at"])

    # Delete every table that FKs to customers/products before the tables
    # themselves, in that order -- SQLite (the test/fallback DB) doesn't
    # enforce foreign keys by default so this only bites against a real
    # Postgres run, and only from the *second* run onward (nothing
    # references customers on a first-ever load).
    db.query(db_models.Prediction).delete()
    db.query(db_models.CustomerSegment).delete()
    db.query(db_models.CustomerExplanation).delete()
    db.query(db_models.Order).delete()
    db.query(db_models.Interaction).delete()
    db.query(db_models.SupportTicket).delete()
    db.query(db_models.Product).delete()
    db.query(db_models.Customer).delete()
    db.commit()

    db.bulk_insert_mappings(db_models.Customer, customers.to_dict(orient="records"))
    db.bulk_insert_mappings(db_models.Product, products.to_dict(orient="records"))
    db.bulk_insert_mappings(db_models.Order, orders.to_dict(orient="records"))
    db.bulk_insert_mappings(db_models.Interaction, interactions.to_dict(orient="records"))
    db.bulk_insert_mappings(db_models.SupportTicket, support.to_dict(orient="records"))
    db.commit()


def raw_tables_seeded(db: Session) -> bool:
    """True once `customers` has any row. build_backend_data.py uses this to
    seed from parquet exactly once instead of wiping rows Kafka/Spark streamed in."""
    return db.query(db_models.Customer).first() is not None


def seed_raw_tables_if_empty(
    db: Session,
    load_frames: Callable[[], tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]],
) -> bool:
    """Seed the raw tables from `load_frames()` only when they are empty.
    Returns False (without calling `load_frames`) if already seeded, so rows
    streamed in by Kafka/Spark are never wiped by a re-run."""
    if raw_tables_seeded(db):
        return False
    customers, products, orders, interactions, support = load_frames()
    load_raw_tables(db, customers, products, orders, interactions, support)
    return True


def read_raw_tables(db: Session) -> dict[str, pd.DataFrame]:
    """Current contents of the raw tables (seed history plus anything streamed
    in since) as the DataFrames the feature pipeline expects."""
    bind = db.get_bind()
    tables = {
        "customers": pd.read_sql(select(db_models.Customer).order_by(db_models.Customer.customer_id), bind),
        "products": pd.read_sql(select(db_models.Product).order_by(db_models.Product.product_id), bind),
        "orders": pd.read_sql(select(db_models.Order).order_by(db_models.Order.order_id), bind),
        "interactions": pd.read_sql(select(db_models.Interaction).order_by(db_models.Interaction.interaction_id), bind),
        "support": pd.read_sql(select(db_models.SupportTicket).order_by(db_models.SupportTicket.ticket_id), bind),
    }
    tables["customers"]["signup_date"] = pd.to_datetime(tables["customers"]["signup_date"])
    tables["orders"]["order_date"] = pd.to_datetime(tables["orders"]["order_date"])
    tables["interactions"]["event_time"] = pd.to_datetime(tables["interactions"]["event_time"])
    tables["support"]["created_at"] = pd.to_datetime(tables["support"]["created_at"])
    return tables


def store_predictions(
    db: Session,
    customer_ids: pd.Series,
    churn_probability: pd.Series | list,
    predicted_clv: pd.Series | list,
    model_version: str,
    prediction_date: date,
) -> None:
    db.query(db_models.Prediction).delete()
    db.commit()
    rows = [
        {
            "customer_id": cid,
            "model_version": model_version,
            "churn_probability": float(cp),
            "predicted_clv": float(clv),
            "prediction_date": prediction_date,
        }
        for cid, cp, clv in zip(customer_ids, churn_probability, predicted_clv)
    ]
    db.bulk_insert_mappings(db_models.Prediction, rows)
    db.commit()


def store_segments(db: Session, customer_ids: pd.Series, segment_labels: pd.Series | list, as_of: date) -> None:
    db.query(db_models.CustomerSegment).delete()
    db.commit()
    rows = [{"customer_id": cid, "segment": seg, "as_of": as_of} for cid, seg in zip(customer_ids, segment_labels)]
    db.bulk_insert_mappings(db_models.CustomerSegment, rows)
    db.commit()


def store_model_run(db: Session, model_name: str, model_version: str, metrics: dict, trained_at: datetime | None = None) -> None:
    trained_at = trained_at or datetime.utcnow()
    db.add(
        db_models.ModelRun(
            model_name=model_name, model_version=model_version, trained_at=trained_at, metrics_json=json.dumps(metrics)
        )
    )
    db.commit()


def store_drift_report(db: Session, report_date: date, model_name: str, rows: list[dict]) -> None:
    """rows: [{kind, metric_name, psi, severity, reference_mean, current_mean}, ...]
    (src/monitoring/drift.py's compute_feature_drift/compute_prediction_drift output,
    reshaped to rows). Replaces prior reports for this model so the API always
    serves the latest run, matching how store_predictions/store_segments behave."""
    db.query(db_models.DriftReport).filter(db_models.DriftReport.model_name == model_name).delete()
    db.commit()
    payload = [
        {
            "report_date": report_date,
            "model_name": model_name,
            "kind": row["kind"],
            "metric_name": row["metric_name"],
            "psi": float(row["psi"]),
            "severity": row["severity"],
            "reference_mean": float(row["reference_mean"]),
            "current_mean": float(row["current_mean"]),
        }
        for row in rows
    ]
    if payload:
        db.bulk_insert_mappings(db_models.DriftReport, payload)
    db.commit()


def store_explanations(
    db: Session,
    customer_ids: pd.Series,
    shap_values,
    X_transformed,
    feature_names: list[str],
    model_version: str,
    prediction_date: date,
    top_n: int = 8,
) -> None:
    db.query(db_models.CustomerExplanation).delete()
    db.commit()

    rows = []
    for i, customer_id in enumerate(customer_ids):
        explanation = local_explanation(shap_values, feature_names, i, X_transformed).head(top_n)
        drivers = [
            {"feature": feature, "shap_value": float(row["shap_value"]), "feature_value": float(row["feature_value"])}
            for feature, row in explanation.iterrows()
        ]
        rows.append(
            {
                "customer_id": customer_id,
                "model_version": model_version,
                "prediction_date": prediction_date,
                "top_drivers_json": json.dumps(drivers),
            }
        )
    db.bulk_insert_mappings(db_models.CustomerExplanation, rows)
    db.commit()
