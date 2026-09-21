from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Customer, DriftReport, Interaction, Order, Prediction, SupportTicket
from api.schemas import DriftMetric, DriftReportResponse, HealthCheck

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

TABLES = {"customers": Customer, "orders": Order, "interactions": Interaction, "support": SupportTicket, "predictions": Prediction}


@router.get("/health", response_model=HealthCheck)
def health(db: Session = Depends(get_db)) -> HealthCheck:
    try:
        table_row_counts = {name: db.scalar(select(func.count()).select_from(model)) or 0 for name, model in TABLES.items()}
        latest_order_date = db.scalar(select(func.max(Order.order_date)))
        latest_prediction_date = db.scalar(select(func.max(Prediction.prediction_date)))
        return HealthCheck(
            status="ok",
            database_connected=True,
            table_row_counts=table_row_counts,
            latest_order_date=latest_order_date,
            latest_prediction_date=latest_prediction_date,
        )
    except Exception:
        return HealthCheck(status="error", database_connected=False, table_row_counts={}, latest_order_date=None, latest_prediction_date=None)


@router.get("/drift/{model_name}", response_model=DriftReportResponse)
def drift_report(model_name: str, db: Session = Depends(get_db)) -> DriftReportResponse:
    rows = db.scalars(
        select(DriftReport).where(DriftReport.model_name == model_name).order_by(DriftReport.psi.desc())
    ).all()
    feature_rows = [r for r in rows if r.kind == "feature"]
    prediction_rows = [r for r in rows if r.kind == "prediction"]
    return DriftReportResponse(
        model_name=model_name,
        report_date=rows[0].report_date if rows else date.today(),
        feature_drift=[DriftMetric(**_row_to_dict(r)) for r in feature_rows],
        prediction_drift=[DriftMetric(**_row_to_dict(r)) for r in prediction_rows],
        has_prediction_baseline=len(prediction_rows) > 0,
    )


def _row_to_dict(row: DriftReport) -> dict:
    return {
        "metric_name": row.metric_name,
        "kind": row.kind,
        "psi": row.psi,
        "severity": row.severity,
        "reference_mean": row.reference_mean,
        "current_mean": row.current_mean,
    }
