from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Customer, CustomerSegment, Prediction
from api.schemas import DashboardSummary, RiskBin, RiskDistribution

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

HIGH_RISK_THRESHOLD = 0.5
RISK_BIN_COUNT = 20


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    total_customers = db.scalar(select(func.count()).select_from(Customer)) or 0
    latest_date = db.scalar(select(func.max(Prediction.prediction_date)))

    if latest_date is None:
        return DashboardSummary(
            total_customers=total_customers,
            scored_customers=0,
            high_risk_count=0,
            mean_churn_probability=0.0,
            revenue_at_risk=0.0,
            mean_predicted_clv=0.0,
            segment_distribution={},
            prediction_date=date.today(),
        )

    scored = db.scalar(
        select(func.count()).select_from(Prediction).where(Prediction.prediction_date == latest_date)
    ) or 0
    mean_churn = db.scalar(
        select(func.avg(Prediction.churn_probability)).where(Prediction.prediction_date == latest_date)
    ) or 0.0
    mean_clv = db.scalar(
        select(func.avg(Prediction.predicted_clv)).where(Prediction.prediction_date == latest_date)
    ) or 0.0
    high_risk_count = db.scalar(
        select(func.count())
        .select_from(Prediction)
        .where(Prediction.prediction_date == latest_date, Prediction.churn_probability >= HIGH_RISK_THRESHOLD)
    ) or 0
    revenue_at_risk = db.scalar(
        select(func.sum(Prediction.predicted_clv)).where(
            Prediction.prediction_date == latest_date, Prediction.churn_probability >= HIGH_RISK_THRESHOLD
        )
    ) or 0.0

    segment_rows = db.execute(select(CustomerSegment.segment, func.count()).group_by(CustomerSegment.segment)).all()
    segment_distribution = {segment: count for segment, count in segment_rows}

    return DashboardSummary(
        total_customers=total_customers,
        scored_customers=scored,
        high_risk_count=high_risk_count,
        mean_churn_probability=float(mean_churn),
        revenue_at_risk=float(revenue_at_risk),
        mean_predicted_clv=float(mean_clv),
        segment_distribution=segment_distribution,
        prediction_date=latest_date,
    )


@router.get("/risk-distribution", response_model=RiskDistribution)
def get_risk_distribution(db: Session = Depends(get_db)) -> RiskDistribution:
    """Histogram of churn probabilities at the latest scoring date, in
    equal-width bins. Binned in Python from one column so it behaves the
    same on Postgres and the SQLite test database."""
    latest_date = db.scalar(select(func.max(Prediction.prediction_date)))
    counts = [0] * RISK_BIN_COUNT
    if latest_date is not None:
        probabilities = db.scalars(
            select(Prediction.churn_probability).where(Prediction.prediction_date == latest_date)
        ).all()
        for probability in probabilities:
            index = min(int(probability * RISK_BIN_COUNT), RISK_BIN_COUNT - 1)
            counts[max(index, 0)] += 1
    width = 1 / RISK_BIN_COUNT
    return RiskDistribution(
        prediction_date=latest_date,
        total=sum(counts),
        bins=[RiskBin(lower=round(i * width, 4), upper=round((i + 1) * width, 4), count=c) for i, c in enumerate(counts)],
    )
