"""Pydantic response models — kept separate from api/models.py (the ORM
layer) so a DB column rename doesn't silently change the API contract."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_customers: int
    scored_customers: int
    high_risk_count: int
    mean_churn_probability: float
    revenue_at_risk: float
    mean_predicted_clv: float
    segment_distribution: dict[str, int]
    prediction_date: date


class RiskBin(BaseModel):
    lower: float
    upper: float
    count: int


class RiskDistribution(BaseModel):
    prediction_date: date | None
    total: int
    bins: list[RiskBin]


class CustomerListItem(BaseModel):
    customer_id: str
    plan: str
    country: str
    acquisition_channel: str
    churn_probability: float | None
    predicted_clv: float | None
    segment: str | None


class CustomerListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CustomerListItem]


class RfmSummary(BaseModel):
    recency_days: float | None
    frequency: int
    monetary: float


class CustomerDetail(BaseModel):
    customer_id: str
    signup_date: date
    country: str
    acquisition_channel: str
    plan: str
    churn_probability: float | None
    predicted_clv: float | None
    segment: str | None
    rfm: RfmSummary


class HistoryEvent(BaseModel):
    event_time: datetime
    event_source: str  # "order" | "interaction" | "support"
    description: str
    amount: float | None = None


class CustomerHistoryResponse(BaseModel):
    customer_id: str
    total_events: int
    events: list[HistoryEvent]


class SegmentSummary(BaseModel):
    segment: str
    size: int
    mean_churn_probability: float
    mean_predicted_clv: float


class ChurnByDimension(BaseModel):
    dimension: str
    value: str
    n: int
    mean_churn_probability: float


class CohortRow(BaseModel):
    cohort_month: str
    cohort_age_months: int
    retained_pct: float


class ModelMetrics(BaseModel):
    model_name: str
    model_version: str
    trained_at: datetime
    metrics: dict[str, float]


class PredictRequest(BaseModel):
    customer_id: str


class ChurnPredictionResponse(BaseModel):
    customer_id: str
    churn_probability: float
    model_version: str


class ClvPredictionResponse(BaseModel):
    customer_id: str
    predicted_clv: float
    model_version: str


class DriverContribution(BaseModel):
    feature: str
    shap_value: float
    feature_value: float


class ExplanationResponse(BaseModel):
    customer_id: str
    model_version: str
    prediction_date: date
    top_drivers: list[DriverContribution]


class DriftMetric(BaseModel):
    metric_name: str
    kind: str  # "feature" | "prediction"
    psi: float
    severity: str
    reference_mean: float
    current_mean: float


class DriftReportResponse(BaseModel):
    model_name: str
    report_date: date
    feature_drift: list[DriftMetric]
    prediction_drift: list[DriftMetric]
    has_prediction_baseline: bool


class HealthCheck(BaseModel):
    status: str
    database_connected: bool
    table_row_counts: dict[str, int]
    latest_order_date: datetime | None
    latest_prediction_date: date | None
