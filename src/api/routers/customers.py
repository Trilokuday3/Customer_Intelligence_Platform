from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Customer, CustomerSegment, Interaction, Order, Prediction, SupportTicket
from api.schemas import (
    CustomerDetail,
    CustomerHistoryResponse,
    CustomerListItem,
    CustomerListResponse,
    HistoryEvent,
    RfmSummary,
)

router = APIRouter(prefix="/customers", tags=["customers"])


def _latest_prediction_date(db: Session):
    return db.scalar(select(func.max(Prediction.prediction_date)))


@router.get("", response_model=CustomerListResponse)
def list_customers(
    db: Session = Depends(get_db),
    search: str | None = None,
    segment: str | None = None,
    plan: str | None = None,
    min_churn_probability: float | None = None,
    max_churn_probability: float | None = None,
    min_predicted_clv: float | None = None,
    sort_by: str = Query("churn_probability", pattern="^(churn_probability|predicted_clv)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> CustomerListResponse:
    latest_date = _latest_prediction_date(db)

    query = (
        select(Customer, Prediction.churn_probability, Prediction.predicted_clv, CustomerSegment.segment)
        .join(
            Prediction,
            (Prediction.customer_id == Customer.customer_id) & (Prediction.prediction_date == latest_date),
            isouter=True,
        )
        .join(CustomerSegment, CustomerSegment.customer_id == Customer.customer_id, isouter=True)
    )
    if search:
        query = query.where(Customer.customer_id.ilike(f"%{search}%"))
    if segment:
        query = query.where(CustomerSegment.segment == segment)
    if plan:
        query = query.where(Customer.plan == plan)
    if min_churn_probability is not None:
        query = query.where(Prediction.churn_probability >= min_churn_probability)
    if max_churn_probability is not None:
        query = query.where(Prediction.churn_probability <= max_churn_probability)
    if min_predicted_clv is not None:
        query = query.where(Prediction.predicted_clv >= min_predicted_clv)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    order_col = Prediction.churn_probability if sort_by == "churn_probability" else Prediction.predicted_clv
    query = query.order_by(order_col.desc().nulls_last()).offset((page - 1) * page_size).limit(page_size)

    rows = db.execute(query).all()
    items = [
        CustomerListItem(
            customer_id=c.customer_id,
            plan=c.plan,
            country=c.country,
            acquisition_channel=c.acquisition_channel,
            churn_probability=churn_p,
            predicted_clv=clv,
            segment=seg,
        )
        for c, churn_p, clv, seg in rows
    ]
    return CustomerListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str, db: Session = Depends(get_db)) -> CustomerDetail:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")

    latest_date = _latest_prediction_date(db)
    prediction = db.execute(
        select(Prediction).where(Prediction.customer_id == customer_id, Prediction.prediction_date == latest_date)
    ).scalar_one_or_none()
    segment_row = db.get(CustomerSegment, customer_id)

    as_of = pd.Timestamp(latest_date) if latest_date else pd.Timestamp.now()
    orders = pd.read_sql(
        select(Order.order_date, Order.amount).where(
            Order.customer_id == customer_id, Order.status == "completed", Order.order_date <= as_of
        ),
        db.bind,
    )
    if orders.empty:
        rfm = RfmSummary(recency_days=None, frequency=0, monetary=0.0)
    else:
        orders["order_date"] = pd.to_datetime(orders["order_date"])
        recency = (as_of - orders["order_date"].max()).days
        rfm = RfmSummary(recency_days=float(recency), frequency=len(orders), monetary=float(orders["amount"].sum()))

    return CustomerDetail(
        customer_id=customer.customer_id,
        signup_date=customer.signup_date,
        country=customer.country,
        acquisition_channel=customer.acquisition_channel,
        plan=customer.plan,
        churn_probability=prediction.churn_probability if prediction else None,
        predicted_clv=prediction.predicted_clv if prediction else None,
        segment=segment_row.segment if segment_row else None,
        rfm=rfm,
    )


@router.get("/{customer_id}/history", response_model=CustomerHistoryResponse)
def get_customer_history(
    customer_id: str, db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=500)
) -> CustomerHistoryResponse:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")

    orders = db.execute(select(Order).where(Order.customer_id == customer_id)).scalars().all()
    interactions = db.execute(select(Interaction).where(Interaction.customer_id == customer_id)).scalars().all()
    tickets = db.execute(select(SupportTicket).where(SupportTicket.customer_id == customer_id)).scalars().all()

    events = [
        HistoryEvent(event_time=o.order_date, event_source="order", description=f"order {o.order_id} ({o.status})", amount=o.amount)
        for o in orders
    ]
    events += [
        HistoryEvent(event_time=i.event_time, event_source="interaction", description=f"{i.event_type} via {i.channel}")
        for i in interactions
    ]
    events += [
        HistoryEvent(event_time=t.created_at, event_source="support", description=f"ticket ({t.category})")
        for t in tickets
    ]
    events.sort(key=lambda e: e.event_time, reverse=True)

    return CustomerHistoryResponse(customer_id=customer_id, total_events=len(events), events=events[:limit])
