from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import Base, engine
from api.routers import analytics, customers, dashboard, explanations, model_center, monitoring, predict, segments

MODELS_DIR = Path(os.environ.get("MODELS_DIR", "models"))
MODEL_VERSION = "xgboost-platt-v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from data import config

    Base.metadata.create_all(bind=engine)
    app.state.reference_cutoff = config.OBSERVATION_CUTOFF
    app.state.model_version = MODEL_VERSION

    churn_path = MODELS_DIR / "churn_xgboost.joblib"
    clv_path = MODELS_DIR / "clv_xgboost.joblib"
    app.state.churn_model = joblib.load(churn_path) if churn_path.exists() else None
    app.state.clv_model = joblib.load(clv_path) if clv_path.exists() else None
    yield


app = FastAPI(title="Customer Intelligence Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(customers.router)
app.include_router(segments.router)
app.include_router(analytics.router)
app.include_router(model_center.router)
app.include_router(predict.router)
app.include_router(explanations.router)
app.include_router(monitoring.router)


@app.get("/")
def root() -> dict:
    return {"service": "customer-intelligence-api", "status": "ok"}
