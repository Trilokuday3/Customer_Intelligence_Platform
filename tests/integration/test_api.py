"""End-to-end API tests against a temp in-memory SQLite DB, populated
via the SAME api.build_data functions scripts/build_backend_data.py uses
against the real dataset — a bug in the loader fails here, on a fast
400-customer fixture, rather than only surfacing on the full run.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.build_data import (
    load_raw_tables,
    store_drift_report,
    store_explanations,
    store_model_run,
    store_predictions,
    store_segments,
)
from api.database import Base, get_db
from api.main import app
from churn.dataset import LABEL_COLUMN as CHURN_LABEL
from churn.dataset import build_snapshot as build_churn_snapshot
from churn.dataset import feature_columns as churn_feature_columns
from churn.evaluate import evaluate_churn_model
from churn.train import predict_churn_probability, train_xgboost
from clv.dataset import LABEL_COLUMN as CLV_LABEL
from clv.dataset import build_snapshot as build_clv_snapshot
from clv.dataset import feature_columns as clv_feature_columns
from clv.evaluate import evaluate_clv_model
from clv.train import predict_clv, train_predictive_clv
from data import config
from explainability.shap_utils import compute_shap_values
from features.behavioral import build_feature_matrix
from monitoring.drift import compute_feature_drift
from segmentation.cluster import fit_kmeans, name_segments_from_profile, prepare_matrix, profile_clusters

TEST_CUTOFF = pd.Timestamp(config.OBSERVATION_CUTOFF)
MODEL_VERSION = "test-v1"


@pytest.fixture(scope="module")
def api_setup(dataset):
    # StaticPool: SQLite's :memory: DB is per-connection, so without a
    # single shared connection each new Session would see an empty DB.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    customers, products, orders, interactions, support = (
        dataset["customers"],
        dataset["products"],
        dataset["orders"],
        dataset["interactions"],
        dataset["support"],
    )

    db = TestingSessionLocal()
    load_raw_tables(db, customers, products, orders, interactions, support)

    churn_snapshot = build_churn_snapshot(customers, orders, interactions, support, products, TEST_CUTOFF)
    churn_feat_cols = churn_feature_columns(churn_snapshot)
    churn_model = train_xgboost(churn_snapshot[churn_feat_cols], churn_snapshot[CHURN_LABEL])
    churn_proba = predict_churn_probability(churn_model, churn_snapshot[churn_feat_cols])
    store_model_run(db, "churn", MODEL_VERSION, evaluate_churn_model(churn_snapshot[CHURN_LABEL], churn_proba))

    clv_snapshot = build_clv_snapshot(customers, orders, interactions, support, products, TEST_CUTOFF)
    clv_feat_cols = clv_feature_columns(clv_snapshot)
    clv_model = train_predictive_clv(clv_snapshot[clv_feat_cols], clv_snapshot[CLV_LABEL])
    clv_pred = predict_clv(clv_model, clv_snapshot[clv_feat_cols])
    store_model_run(db, "clv", MODEL_VERSION, evaluate_clv_model(clv_snapshot[CLV_LABEL], clv_pred))

    clv_pred_by_id = dict(zip(clv_snapshot["customer_id"], clv_pred))
    aligned_clv = [clv_pred_by_id.get(cid, 0.0) for cid in churn_snapshot["customer_id"]]
    store_predictions(db, churn_snapshot["customer_id"], churn_proba, aligned_clv, MODEL_VERSION, TEST_CUTOFF.date())

    feature_matrix = build_feature_matrix(customers, orders, interactions, support, products, TEST_CUTOFF)
    X_scaled, _ = prepare_matrix(feature_matrix)
    kmeans = fit_kmeans(X_scaled, k=4)
    fm_clustered = feature_matrix.copy()
    fm_clustered["cluster"] = kmeans.labels_
    profile = profile_clusters(fm_clustered)
    names = name_segments_from_profile(profile)
    segment_labels = [names[c] for c in kmeans.labels_]
    store_segments(db, feature_matrix["customer_id"], segment_labels, TEST_CUTOFF.date())

    shap_values, X_transformed, feature_names = compute_shap_values(churn_model, churn_snapshot[churn_feat_cols])
    store_explanations(
        db, churn_snapshot["customer_id"], shap_values, X_transformed, feature_names, MODEL_VERSION, TEST_CUTOFF.date()
    )

    # Reference == current here (no second historical snapshot in this fixture), so PSI
    # should come back ~0/stable -- this exercises storage + the API shape, not real drift.
    churn_drift = compute_feature_drift(churn_snapshot[churn_feat_cols], churn_snapshot[churn_feat_cols], churn_feat_cols)
    drift_rows = [
        {
            "kind": "feature",
            "metric_name": row.feature,
            "psi": row.psi,
            "severity": row.severity,
            "reference_mean": row.reference_mean,
            "current_mean": row.current_mean,
        }
        for row in churn_drift.itertuples()
    ]
    store_drift_report(db, TEST_CUTOFF.date(), "churn", drift_rows)
    db.close()

    with TestClient(app) as client:
        client.app.state.churn_model = churn_model
        client.app.state.clv_model = clv_model
        client.app.state.model_version = MODEL_VERSION
        client.app.state.reference_cutoff = config.OBSERVATION_CUTOFF
        yield {
            "client": client,
            "churn_snapshot": churn_snapshot,
            "churn_proba": churn_proba,
            "clv_pred_by_id": clv_pred_by_id,
            "n_customers": len(customers),
            "segment_names": sorted(set(segment_labels)),
        }

    app.dependency_overrides.clear()


class TestHealthAndRoot:
    def test_root(self, api_setup):
        resp = api_setup["client"].get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_reports_row_counts(self, api_setup):
        resp = api_setup["client"].get("/monitoring/health")
        body = resp.json()
        assert resp.status_code == 200
        assert body["database_connected"] is True
        assert body["table_row_counts"]["customers"] == api_setup["n_customers"]


class TestDashboard:
    def test_summary_matches_stored_predictions(self, api_setup):
        resp = api_setup["client"].get("/dashboard/summary")
        body = resp.json()
        assert resp.status_code == 200
        assert body["total_customers"] == api_setup["n_customers"]
        assert body["scored_customers"] == len(api_setup["churn_snapshot"])
        assert sum(body["segment_distribution"].values()) == api_setup["n_customers"]


    def test_risk_distribution_bins_every_scored_customer(self, api_setup):
        resp = api_setup["client"].get("/dashboard/risk-distribution")
        body = resp.json()
        assert resp.status_code == 200
        assert body["total"] == len(api_setup["churn_snapshot"])
        assert sum(b["count"] for b in body["bins"]) == body["total"]
        assert len(body["bins"]) == 20
        assert body["bins"][0]["lower"] == 0.0 and body["bins"][-1]["upper"] == 1.0


class TestCustomers:
    def test_list_returns_all_customers(self, api_setup):
        resp = api_setup["client"].get("/customers", params={"page_size": 5})
        body = resp.json()
        assert resp.status_code == 200
        assert body["total"] == api_setup["n_customers"]
        assert len(body["items"]) == 5

    def test_list_filter_by_min_churn_probability(self, api_setup):
        resp = api_setup["client"].get("/customers", params={"min_churn_probability": 0.9, "page_size": 200})
        body = resp.json()
        assert all(item["churn_probability"] >= 0.9 for item in body["items"])

    def test_detail_for_scored_customer_has_prediction_and_rfm(self, api_setup):
        customer_id = api_setup["churn_snapshot"]["customer_id"].iloc[0]
        resp = api_setup["client"].get(f"/customers/{customer_id}")
        body = resp.json()
        assert resp.status_code == 200
        assert body["churn_probability"] is not None
        assert body["segment"] in api_setup["segment_names"]
        assert body["rfm"]["frequency"] >= 0

    def test_detail_for_unknown_customer_is_404(self, api_setup):
        resp = api_setup["client"].get("/customers/NOT-A-REAL-ID")
        assert resp.status_code == 404

    def test_history_returns_events_sorted_descending(self, api_setup):
        customer_id = api_setup["churn_snapshot"]["customer_id"].iloc[0]
        resp = api_setup["client"].get(f"/customers/{customer_id}/history")
        body = resp.json()
        assert resp.status_code == 200
        times = [e["event_time"] for e in body["events"]]
        assert times == sorted(times, reverse=True)


class TestSegments:
    def test_list_segments_covers_all_named_segments(self, api_setup):
        resp = api_setup["client"].get("/segments")
        body = resp.json()
        assert resp.status_code == 200
        assert {s["segment"] for s in body} == set(api_setup["segment_names"])

    def test_segment_detail_has_top_at_risk(self, api_setup):
        segment = api_setup["segment_names"][0]
        resp = api_setup["client"].get(f"/segments/{segment}")
        body = resp.json()
        assert resp.status_code == 200
        assert body["summary"]["segment"] == segment
        assert len(body["top_at_risk"]) > 0

    def test_unknown_segment_is_404(self, api_setup):
        resp = api_setup["client"].get("/segments/not-a-segment")
        assert resp.status_code == 404


class TestAnalytics:
    def test_churn_by_plan(self, api_setup):
        resp = api_setup["client"].get("/analytics/churn", params={"dimension": "plan"})
        body = resp.json()
        assert resp.status_code == 200
        assert {row["value"] for row in body} <= {"bronze", "silver", "gold"}

    def test_cohorts_returns_percentages(self, api_setup):
        resp = api_setup["client"].get("/analytics/cohorts")
        body = resp.json()
        assert resp.status_code == 200
        assert len(body) > 0
        assert all(0 <= row["retained_pct"] <= 100 for row in body)


class TestModelCenter:
    def test_churn_metrics(self, api_setup):
        resp = api_setup["client"].get("/models/churn")
        body = resp.json()
        assert resp.status_code == 200
        assert body["model_version"] == MODEL_VERSION
        assert "pr_auc" in body["metrics"]

    def test_unknown_model_is_404(self, api_setup):
        resp = api_setup["client"].get("/models/not-a-model")
        assert resp.status_code == 404


class TestPredict:
    def test_predict_churn_matches_stored_batch_prediction(self, api_setup):
        idx = 0
        customer_id = api_setup["churn_snapshot"]["customer_id"].iloc[idx]
        expected = float(api_setup["churn_proba"][idx])

        resp = api_setup["client"].post("/predict/churn", json={"customer_id": customer_id})
        body = resp.json()
        assert resp.status_code == 200
        assert body["churn_probability"] == pytest.approx(expected, abs=1e-6)

    def test_predict_clv_matches_stored_batch_prediction(self, api_setup):
        customer_id = next(iter(api_setup["clv_pred_by_id"]))
        expected = api_setup["clv_pred_by_id"][customer_id]

        resp = api_setup["client"].post("/predict/clv", json={"customer_id": customer_id})
        body = resp.json()
        assert resp.status_code == 200
        assert body["predicted_clv"] == pytest.approx(expected, abs=1e-6)

    def test_predict_unknown_customer_is_404(self, api_setup):
        resp = api_setup["client"].post("/predict/churn", json={"customer_id": "NOT-A-REAL-ID"})
        assert resp.status_code == 404


class TestMonitoring:
    def test_drift_report_returns_stable_feature_metrics(self, api_setup):
        resp = api_setup["client"].get("/monitoring/drift/churn")
        body = resp.json()
        assert resp.status_code == 200
        assert body["model_name"] == "churn"
        assert len(body["feature_drift"]) > 0
        assert all(row["severity"] == "stable" for row in body["feature_drift"])
        assert body["has_prediction_baseline"] is False

    def test_drift_report_for_unscored_model_is_empty(self, api_setup):
        resp = api_setup["client"].get("/monitoring/drift/clv")
        body = resp.json()
        assert resp.status_code == 200
        assert body["feature_drift"] == []
        assert body["has_prediction_baseline"] is False


class TestExplanations:
    def test_returns_top_drivers_for_scored_customer(self, api_setup):
        customer_id = api_setup["churn_snapshot"]["customer_id"].iloc[0]
        resp = api_setup["client"].get(f"/explanations/{customer_id}")
        body = resp.json()
        assert resp.status_code == 200
        assert len(body["top_drivers"]) == 8

    def test_unknown_customer_is_404(self, api_setup):
        resp = api_setup["client"].get("/explanations/NOT-A-REAL-ID")
        assert resp.status_code == 404
