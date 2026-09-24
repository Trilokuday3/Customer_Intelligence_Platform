"""/predict/* must score as of the stored predictions' date (so it keeps
matching the batch output once the batch job scores at the newest data
day), and fall back to the app's reference cutoff when nothing is stored."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import models as db_models
from api.build_data import load_raw_tables, store_predictions
from api.database import Base, get_db
from api.main import app
from churn.dataset import LABEL_COLUMN, build_snapshot, feature_columns
from churn.train import predict_churn_probability, train_xgboost
from data import config
from scoring.snapshot import build_scoring_snapshot

REFERENCE = pd.Timestamp(config.OBSERVATION_CUTOFF)
STORED_DATE = pd.Timestamp("2025-09-30")


@pytest.fixture(scope="module")
def env(dataset):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    args = (dataset["customers"], dataset["orders"], dataset["interactions"], dataset["support"], dataset["products"])

    db = Session()
    load_raw_tables(db, dataset["customers"], dataset["products"], dataset["orders"], dataset["interactions"], dataset["support"])
    train = build_snapshot(*args, pd.Timestamp("2025-06-30"))
    cols = feature_columns(train)
    model = train_xgboost(train[cols], train[LABEL_COLUMN])

    with TestClient(app) as client:
        client.app.state.churn_model = model
        client.app.state.clv_model = None
        client.app.state.model_version = "test-v1"
        client.app.state.reference_cutoff = config.OBSERVATION_CUTOFF
        yield {"client": client, "db": db, "model": model, "cols": cols, "args": args}
    app.dependency_overrides.clear()
    db.close()


def _expected(env, as_of):
    snap = build_scoring_snapshot(*env["args"], as_of)
    proba = predict_churn_probability(env["model"], snap[env["cols"]])
    return dict(zip(snap["customer_id"], proba))


def _clear_predictions(db):
    db.query(db_models.Prediction).delete()
    db.commit()


def test_falls_back_to_the_reference_cutoff_when_no_predictions_are_stored(env):
    _clear_predictions(env["db"])
    expected = _expected(env, REFERENCE)
    customer_id = next(iter(expected))
    resp = env["client"].post("/predict/churn", json={"customer_id": customer_id})
    assert resp.status_code == 200
    assert resp.json()["churn_probability"] == pytest.approx(expected[customer_id])


def test_follows_the_stored_prediction_date_instead_of_the_reference_cutoff(env):
    at_stored = _expected(env, STORED_DATE)
    at_reference = _expected(env, REFERENCE)
    shared = [c for c in at_stored if c in at_reference]
    # pick the customer whose score moves most between the two dates, so the
    # assertion can only pass if the stored date was really used
    customer_id = max(shared, key=lambda c: abs(at_stored[c] - at_reference[c]))
    assert abs(at_stored[customer_id] - at_reference[customer_id]) > 1e-4

    _clear_predictions(env["db"])
    store_predictions(env["db"], pd.Series([customer_id]), [0.5], [100.0], "test-v1", STORED_DATE.date())
    try:
        resp = env["client"].post("/predict/churn", json={"customer_id": customer_id})
    finally:
        _clear_predictions(env["db"])

    assert resp.status_code == 200
    assert resp.json()["churn_probability"] == pytest.approx(at_stored[customer_id])
