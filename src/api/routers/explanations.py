from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import CustomerExplanation
from api.schemas import DriverContribution, ExplanationResponse

router = APIRouter(prefix="/explanations", tags=["explanations"])


@router.get("/{customer_id}", response_model=ExplanationResponse)
def get_explanation(customer_id: str, db: Session = Depends(get_db)) -> ExplanationResponse:
    row = db.get(CustomerExplanation, customer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no explanation available for this customer")

    drivers = [DriverContribution(**d) for d in json.loads(row.top_drivers_json)]
    return ExplanationResponse(
        customer_id=customer_id,
        model_version=row.model_version,
        prediction_date=row.prediction_date,
        top_drivers=drivers,
    )
