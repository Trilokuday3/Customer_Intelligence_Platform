"""Cohort retention is computed in pandas rather than raw SQL: Postgres'
date_trunc and SQLite's strftime aren't portable to a single query, and
this endpoint needs to run against both (Postgres in production, SQLite
in tests) without maintaining two SQL dialects. Churn-by-dimension uses
real SQL aggregation since GROUP BY is portable."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Customer, Order, Prediction
from api.schemas import ChurnByDimension, CohortRow

router = APIRouter(prefix="/analytics", tags=["analytics"])

DIMENSION_COLUMNS = {"plan": Customer.plan, "acquisition_channel": Customer.acquisition_channel, "country": Customer.country}


@router.get("/churn", response_model=list[ChurnByDimension])
def churn_by_dimension(
    db: Session = Depends(get_db), dimension: str = Query("plan", pattern="^(plan|acquisition_channel|country)$")
) -> list[ChurnByDimension]:
    latest_date = db.scalar(select(func.max(Prediction.prediction_date)))
    col = DIMENSION_COLUMNS[dimension]
    rows = db.execute(
        select(col, func.count(), func.avg(Prediction.churn_probability))
        .join(Prediction, (Prediction.customer_id == Customer.customer_id) & (Prediction.prediction_date == latest_date))
        .group_by(col)
    ).all()
    return [ChurnByDimension(dimension=dimension, value=str(value), n=n, mean_churn_probability=float(avg or 0.0)) for value, n, avg in rows]


@router.get("/cohorts", response_model=list[CohortRow])
def cohort_retention(db: Session = Depends(get_db), max_cohort_age_months: int = Query(6, ge=1, le=24)) -> list[CohortRow]:
    customers = pd.read_sql(select(Customer.customer_id, Customer.signup_date), db.bind)
    orders = pd.read_sql(select(Order.customer_id, Order.order_date).where(Order.status == "completed"), db.bind)

    customers["signup_date"] = pd.to_datetime(customers["signup_date"])
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    customers["cohort_month"] = customers["signup_date"].dt.to_period("M")

    merged = orders.merge(customers[["customer_id", "cohort_month"]], on="customer_id")
    merged["order_month"] = merged["order_date"].dt.to_period("M")
    merged["cohort_age"] = (merged["order_month"] - merged["cohort_month"]).apply(lambda x: x.n)
    merged = merged[(merged["cohort_age"] >= 0) & (merged["cohort_age"] <= max_cohort_age_months)]

    cohort_sizes = customers.groupby("cohort_month").size()
    retained = merged.groupby(["cohort_month", "cohort_age"])["customer_id"].nunique()

    rows = []
    for (cohort_month, cohort_age), n_retained in retained.items():
        size = cohort_sizes.loc[cohort_month]
        rows.append(
            CohortRow(cohort_month=str(cohort_month), cohort_age_months=int(cohort_age), retained_pct=round(n_retained / size * 100, 2))
        )
    return sorted(rows, key=lambda r: (r.cohort_month, r.cohort_age_months))
