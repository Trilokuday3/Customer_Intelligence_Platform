from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Customer, CustomerSegment, Prediction
from api.schemas import CustomerListItem, SegmentSummary

router = APIRouter(prefix="/segments", tags=["segments"])


def _latest_prediction_date(db: Session):
    return db.scalar(select(func.max(Prediction.prediction_date)))


@router.get("", response_model=list[SegmentSummary])
def list_segments(db: Session = Depends(get_db)) -> list[SegmentSummary]:
    latest_date = _latest_prediction_date(db)
    rows = db.execute(
        select(
            CustomerSegment.segment,
            func.count(),
            func.avg(Prediction.churn_probability),
            func.avg(Prediction.predicted_clv),
        )
        .join(
            Prediction,
            (Prediction.customer_id == CustomerSegment.customer_id) & (Prediction.prediction_date == latest_date),
        )
        .group_by(CustomerSegment.segment)
    ).all()
    return [
        SegmentSummary(segment=segment, size=size, mean_churn_probability=float(mc or 0.0), mean_predicted_clv=float(mclv or 0.0))
        for segment, size, mc, mclv in rows
    ]


@router.get("/{segment_name}")
def get_segment(segment_name: str, db: Session = Depends(get_db)) -> dict:
    latest_date = _latest_prediction_date(db)
    summary_row = db.execute(
        select(
            func.count(),
            func.avg(Prediction.churn_probability),
            func.avg(Prediction.predicted_clv),
        )
        .select_from(CustomerSegment)
        .join(
            Prediction,
            (Prediction.customer_id == CustomerSegment.customer_id) & (Prediction.prediction_date == latest_date),
        )
        .where(CustomerSegment.segment == segment_name)
    ).one()
    size, mean_churn, mean_clv = summary_row
    if not size:
        raise HTTPException(status_code=404, detail="unknown segment")

    top_at_risk_rows = db.execute(
        select(Customer, Prediction.churn_probability, Prediction.predicted_clv)
        .join(CustomerSegment, CustomerSegment.customer_id == Customer.customer_id)
        .join(
            Prediction,
            (Prediction.customer_id == Customer.customer_id) & (Prediction.prediction_date == latest_date),
        )
        .where(CustomerSegment.segment == segment_name)
        .order_by(Prediction.churn_probability.desc())
        .limit(10)
    ).all()

    top_at_risk = [
        CustomerListItem(
            customer_id=c.customer_id,
            plan=c.plan,
            country=c.country,
            acquisition_channel=c.acquisition_channel,
            churn_probability=churn_p,
            predicted_clv=clv,
            segment=segment_name,
        )
        for c, churn_p, clv in top_at_risk_rows
    ]

    return {
        "summary": SegmentSummary(
            segment=segment_name, size=size, mean_churn_probability=float(mean_churn or 0.0), mean_predicted_clv=float(mean_clv or 0.0)
        ),
        "top_at_risk": top_at_risk,
    }
