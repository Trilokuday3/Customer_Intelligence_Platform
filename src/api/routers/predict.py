"""On-demand scoring — distinct from the batch-precomputed `predictions`
table the other routers read. Recomputes this one customer's features
live from the DB as of the app's reference cutoff and runs it through
the already-trained model loaded at startup (api/main.py). Because it
uses the same cutoff and feature code as the batch job, its output
should match the stored prediction for the same customer exactly — see
tests/integration/test_api.py for that as an explicit consistency check.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Customer, Interaction, Order, Product, SupportTicket
from api.schemas import ChurnPredictionResponse, ClvPredictionResponse, PredictRequest

router = APIRouter(prefix="/predict", tags=["predict"])


def _build_single_customer_frame(customer_id: str, db: Session) -> dict[str, pd.DataFrame]:
    customers = pd.read_sql(select(Customer).where(Customer.customer_id == customer_id), db.bind)
    if customers.empty:
        raise HTTPException(status_code=404, detail="customer not found")

    orders = pd.read_sql(select(Order).where(Order.customer_id == customer_id), db.bind)
    interactions = pd.read_sql(select(Interaction).where(Interaction.customer_id == customer_id), db.bind)
    support = pd.read_sql(select(SupportTicket).where(SupportTicket.customer_id == customer_id), db.bind)
    products = pd.read_sql(select(Product), db.bind)

    for df, col in [(orders, "order_date"), (interactions, "event_time"), (support, "created_at")]:
        if not df.empty:
            df[col] = pd.to_datetime(df[col])
    customers["signup_date"] = pd.to_datetime(customers["signup_date"])

    return {"customers": customers, "orders": orders, "interactions": interactions, "support": support, "products": products}


def _score(request: Request, db: Session, customer_id: str, model_attr: str):
    model = getattr(request.app.state, model_attr, None)
    if model is None:
        raise HTTPException(status_code=503, detail=f"{model_attr} not loaded — run scripts/build_backend_data.py first")

    from features.behavioral import build_feature_matrix

    tables = _build_single_customer_frame(customer_id, db)
    as_of = pd.Timestamp(request.app.state.reference_cutoff)
    feature_matrix = build_feature_matrix(
        tables["customers"], tables["orders"], tables["interactions"], tables["support"], tables["products"], as_of
    )
    feature_columns = [c for c in feature_matrix.columns if c != "customer_id"]
    return model, feature_matrix[feature_columns]


@router.post("/churn", response_model=ChurnPredictionResponse)
def predict_churn(payload: PredictRequest, request: Request, db: Session = Depends(get_db)) -> ChurnPredictionResponse:
    model, X = _score(request, db, payload.customer_id, "churn_model")
    probability = float(model.predict_proba(X)[0, 1])
    return ChurnPredictionResponse(
        customer_id=payload.customer_id, churn_probability=probability, model_version=request.app.state.model_version
    )


@router.post("/clv", response_model=ClvPredictionResponse)
def predict_clv(payload: PredictRequest, request: Request, db: Session = Depends(get_db)) -> ClvPredictionResponse:
    model, X = _score(request, db, payload.customer_id, "clv_model")
    value = float(max(model.predict(X)[0], 0.0))
    return ClvPredictionResponse(
        customer_id=payload.customer_id, predicted_clv=value, model_version=request.app.state.model_version
    )
