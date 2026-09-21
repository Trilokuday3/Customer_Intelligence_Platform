from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import ModelRun
from api.schemas import ModelMetrics

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/{model_name}", response_model=ModelMetrics)
def get_model_metrics(model_name: str, db: Session = Depends(get_db)) -> ModelMetrics:
    if model_name not in ("churn", "clv"):
        raise HTTPException(status_code=404, detail="unknown model — use 'churn' or 'clv'")

    row = db.execute(
        select(ModelRun).where(ModelRun.model_name == model_name).order_by(ModelRun.trained_at.desc())
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="no trained model run recorded for this model")

    return ModelMetrics(
        model_name=row.model_name,
        model_version=row.model_version,
        trained_at=row.trained_at,
        metrics=json.loads(row.metrics_json),
    )
