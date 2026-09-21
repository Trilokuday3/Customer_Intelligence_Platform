"""SQLAlchemy ORM models. Column-for-column mirror of src/data/schemas.py
(the pydantic generation schema) plus three tables that only exist on
the serving side: predictions, customer_segments, model_runs,
customer_explanations — the batch-scoring outputs a real deployment
would compute offline and a request-time API only reads (guide section
21: "Batch/background jobs for predictions ... FastAPI Inference")."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    signup_date: Mapped[date] = mapped_column(Date)
    country: Mapped[str] = mapped_column(String)
    acquisition_channel: Mapped[str] = mapped_column(String)
    plan: Mapped[str] = mapped_column(String)


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), index=True)
    order_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.product_id"))
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)


class Interaction(Base):
    __tablename__ = "interactions"

    interaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_type: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)


class SupportTicket(Base):
    __tablename__ = "support"

    ticket_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    category: Mapped[str] = mapped_column(String)


class Prediction(Base):
    """Batch-scored churn/CLV output — one row per (customer, model
    version, prediction_date). Dashboard/customer endpoints read this
    table; they never re-run a model per request."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), index=True)
    model_version: Mapped[str] = mapped_column(String)
    churn_probability: Mapped[float] = mapped_column(Float)
    predicted_clv: Mapped[float] = mapped_column(Float)
    prediction_date: Mapped[date] = mapped_column(Date, index=True)

    __table_args__ = (Index("ix_predictions_customer_date", "customer_id", "prediction_date"),)


class CustomerSegment(Base):
    __tablename__ = "customer_segments"

    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), primary_key=True)
    segment: Mapped[str] = mapped_column(String, index=True)
    as_of: Mapped[date] = mapped_column(Date)


class ModelRun(Base):
    """Evaluation metrics for one trained model version — a lightweight
    stand-in for the MLflow model registry that arrives in Phase 11.
    Populated once by scripts/build_backend_data.py, never computed
    inline in a request handler (guide 36: don't hard-code dashboard
    metrics — these ARE computed, just computed offline and cached)."""

    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String, index=True)  # "churn" | "clv"
    model_version: Mapped[str] = mapped_column(String)
    trained_at: Mapped[datetime] = mapped_column(DateTime)
    metrics_json: Mapped[str] = mapped_column(String)  # json.dumps(dict)


class DriftReport(Base):
    """PSI drift result for one metric (a feature, or a model's
    prediction distribution) from one monitoring run. `kind` separates
    input-feature drift from output-prediction drift so the dashboard
    can group them; `reference_mean`/`current_mean` let a human see
    direction, since PSI alone is only a magnitude (src/monitoring/drift.py)."""

    __tablename__ = "drift_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    model_name: Mapped[str] = mapped_column(String, index=True)  # "churn" | "clv"
    kind: Mapped[str] = mapped_column(String)  # "feature" | "prediction"
    metric_name: Mapped[str] = mapped_column(String)  # feature name, or "churn_probability" / "predicted_clv"
    psi: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String)  # "stable" | "moderate" | "significant"
    reference_mean: Mapped[float] = mapped_column(Float)
    current_mean: Mapped[float] = mapped_column(Float)


class CustomerExplanation(Base):
    """Precomputed top-N local SHAP contributions per customer, so
    GET /explanations/{id} is a lookup, not a per-request SHAP run."""

    __tablename__ = "customer_explanations"

    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), primary_key=True)
    model_version: Mapped[str] = mapped_column(String)
    prediction_date: Mapped[date] = mapped_column(Date)
    top_drivers_json: Mapped[str] = mapped_column(String)  # json.dumps([{feature, shap_value, feature_value}, ...])
