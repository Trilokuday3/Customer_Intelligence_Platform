"""One-shot batch job: load raw data, train/persist the champion churn
and CLV models, and compute predictions/segments/explanations into the
API's database. Mirrors what a real Phase 11 scheduled retraining job
would do; run manually for now.

Usage:
    .venv/Scripts/python.exe scripts/build_backend_data.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api.build_data import (  # noqa: E402
    load_raw_tables,
    store_drift_report,
    store_explanations,
    store_model_run,
    store_predictions,
    store_segments,
)
from api.database import Base, SessionLocal, engine  # noqa: E402
from api.models import Prediction  # noqa: E402
from churn.dataset import LABEL_COLUMN as CHURN_LABEL  # noqa: E402
from churn.dataset import build_snapshot as build_churn_snapshot  # noqa: E402
from churn.dataset import build_training_pool as build_churn_pool  # noqa: E402
from churn.dataset import feature_columns as churn_feature_columns  # noqa: E402
from churn.evaluate import evaluate_churn_model  # noqa: E402
from churn.train import predict_churn_probability, train_xgboost as train_churn_xgboost  # noqa: E402
from clv.dataset import LABEL_COLUMN as CLV_LABEL  # noqa: E402
from clv.dataset import build_snapshot as build_clv_snapshot  # noqa: E402
from clv.dataset import build_training_pool as build_clv_pool  # noqa: E402
from clv.dataset import feature_columns as clv_feature_columns  # noqa: E402
from clv.evaluate import evaluate_clv_model  # noqa: E402
from clv.train import predict_clv, train_predictive_clv  # noqa: E402
from data import config  # noqa: E402
from explainability.shap_utils import compute_shap_values  # noqa: E402
from features.behavioral import build_feature_matrix  # noqa: E402
from monitoring.drift import compute_feature_drift, compute_prediction_drift  # noqa: E402
from segmentation.cluster import fit_kmeans, name_segments_from_profile, prepare_matrix, profile_clusters  # noqa: E402

MODELS_DIR = ROOT / "models"
MODEL_VERSION = "xgboost-v1"
MLFLOW_EXPERIMENT = "customer-intelligence"


def _log_to_mlflow(model_name: str, model, params: dict, metrics: dict) -> None:
    """Experiment tracking + model registry (Phase 11). Defaults to a local
    SQLite-backed store (`mlflow.db`, gitignored via the *.db rule) with
    artifacts in `mlruns/` -- MLflow 3's raw filesystem-only backend is in
    maintenance mode and refuses new writes, so a bare `file:./mlruns`
    tracking URI raises rather than just warning. `mlflow ui --backend-store-uri
    sqlite:///mlflow.db` reads it directly, no server required. Set
    MLFLOW_TRACKING_URI (see .env.example) to point at a running `mlflow
    server` instead. Failures here are logged, not fatal: a missing/broken
    MLflow setup shouldn't block the batch job that feeds the live dashboard."""
    try:
        import mlflow
        import mlflow.sklearn
    except ImportError:
        print(f"  [mlflow] not installed, skipping tracking for {model_name} (pip install -e '.[mlops]')")
        return

    try:
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}"))
        if mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT) is None:
            mlflow.create_experiment(MLFLOW_EXPERIMENT, artifact_location=f"file:{(ROOT / 'mlruns').as_posix()}")
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name=f"{model_name}-{MODEL_VERSION}"):
            mlflow.log_params(params)
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
            # MLflow 3's default serialization ("skops") refuses to deserialize
            # XGBoost estimators inside a sklearn Pipeline as "untrusted types" --
            # cloudpickle is the conventional choice for exactly this case.
            mlflow.sklearn.log_model(
                model, "model", serialization_format="cloudpickle", registered_model_name=f"customer-intelligence-{model_name}"
            )
    except Exception as exc:  # pragma: no cover - best-effort tracking, never blocks the batch job
        print(f"  [mlflow] logging failed for {model_name}: {exc}")


def _drift_rows_from_features(drift_df) -> list[dict]:
    return [
        {
            "kind": "feature",
            "metric_name": row.feature,
            "psi": row.psi,
            "severity": row.severity,
            "reference_mean": row.reference_mean,
            "current_mean": row.current_mean,
        }
        for row in drift_df.itertuples()
    ]


CHURN_TRAIN_CUTOFFS = ["2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30"]
CLV_TRAIN_CUTOFFS = ["2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30"]


def main() -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    raw = ROOT / "data" / "raw"
    customers = pd.read_parquet(raw / "customers.parquet")
    products = pd.read_parquet(raw / "products.parquet")
    orders = pd.read_parquet(raw / "orders.parquet")
    interactions = pd.read_parquet(raw / "interactions.parquet")
    support = pd.read_parquet(raw / "support.parquet")

    test_cutoff = pd.Timestamp(config.OBSERVATION_CUTOFF)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("loading raw tables...")
        load_raw_tables(db, customers, products, orders, interactions, support)

        # Captured before store_predictions() overwrites the table -- the only
        # "current vs. last run" baseline available for prediction drift.
        previous_predictions = db.query(Prediction).all()
        previous_churn_proba = [p.churn_probability for p in previous_predictions]
        previous_clv_pred = [p.predicted_clv for p in previous_predictions]

        print("training churn model...")
        churn_cutoffs = [pd.Timestamp(d) for d in CHURN_TRAIN_CUTOFFS]
        churn_pool = build_churn_pool(customers, orders, interactions, support, products, churn_cutoffs)
        churn_feat_cols = churn_feature_columns(churn_pool)
        churn_model = train_churn_xgboost(churn_pool[churn_feat_cols], churn_pool[CHURN_LABEL])

        churn_test = build_churn_snapshot(customers, orders, interactions, support, products, test_cutoff)
        churn_test_proba = predict_churn_probability(churn_model, churn_test[churn_feat_cols])
        churn_metrics = evaluate_churn_model(churn_test[CHURN_LABEL], churn_test_proba)
        joblib.dump(churn_model, MODELS_DIR / "churn_xgboost.joblib")
        store_model_run(db, "churn", MODEL_VERSION, churn_metrics)
        print("  churn PR-AUC:", round(churn_metrics["pr_auc"], 3))
        _log_to_mlflow(
            "churn",
            churn_model,
            params={"cutoffs": ",".join(CHURN_TRAIN_CUTOFFS), "n_features": len(churn_feat_cols), "model_version": MODEL_VERSION},
            metrics=churn_metrics,
        )

        print("training clv model...")
        clv_cutoffs = [pd.Timestamp(d) for d in CLV_TRAIN_CUTOFFS]
        clv_pool = build_clv_pool(customers, orders, interactions, support, products, clv_cutoffs)
        clv_feat_cols = clv_feature_columns(clv_pool)
        clv_model = train_predictive_clv(clv_pool[clv_feat_cols], clv_pool[CLV_LABEL])

        clv_test = build_clv_snapshot(customers, orders, interactions, support, products, test_cutoff)
        clv_test_pred = predict_clv(clv_model, clv_test[clv_feat_cols])
        clv_metrics = evaluate_clv_model(clv_test[CLV_LABEL], clv_test_pred)
        joblib.dump(clv_model, MODELS_DIR / "clv_xgboost.joblib")
        store_model_run(db, "clv", MODEL_VERSION, clv_metrics)
        print("  clv MAE:", round(clv_metrics["mae"], 2))
        _log_to_mlflow(
            "clv",
            clv_model,
            params={"cutoffs": ",".join(CLV_TRAIN_CUTOFFS), "n_features": len(clv_feat_cols), "model_version": MODEL_VERSION},
            metrics=clv_metrics,
        )

        print("checking drift (training pool vs. latest snapshot, and vs. the last scoring run)...")
        churn_feature_drift = compute_feature_drift(churn_pool[churn_feat_cols], churn_test[churn_feat_cols], churn_feat_cols)
        clv_feature_drift = compute_feature_drift(clv_pool[clv_feat_cols], clv_test[clv_feat_cols], clv_feat_cols)
        churn_drift_rows = _drift_rows_from_features(churn_feature_drift)
        clv_drift_rows = _drift_rows_from_features(clv_feature_drift)
        if previous_churn_proba:
            churn_pred_drift = compute_prediction_drift(previous_churn_proba, churn_test_proba)
            churn_drift_rows.append({"kind": "prediction", "metric_name": "churn_probability", **churn_pred_drift})
        if previous_clv_pred:
            clv_pred_drift = compute_prediction_drift(previous_clv_pred, clv_test_pred)
            clv_drift_rows.append({"kind": "prediction", "metric_name": "predicted_clv", **clv_pred_drift})
        store_drift_report(db, test_cutoff.date(), "churn", churn_drift_rows)
        store_drift_report(db, test_cutoff.date(), "clv", clv_drift_rows)
        n_significant = sum(1 for r in churn_drift_rows + clv_drift_rows if r["severity"] == "significant")
        print(f"  {n_significant} metric(s) flagged significant drift" if n_significant else "  no significant drift")

        print("storing predictions for the active-at-cutoff population...")
        # churn and clv snapshots share the same eligibility rule (active_lookback_days=180
        # on the same qualifying orders), so they cover the same customer population --
        # merge defensively rather than assuming identical row order.
        clv_pred_by_id = dict(zip(clv_test["customer_id"], clv_test_pred))
        aligned_clv_pred = [clv_pred_by_id.get(cid, 0.0) for cid in churn_test["customer_id"]]
        store_predictions(
            db, churn_test["customer_id"], churn_test_proba, aligned_clv_pred, MODEL_VERSION, test_cutoff.date()
        )

        print("computing segments...")
        feature_matrix = build_feature_matrix(customers, orders, interactions, support, products, test_cutoff)
        X_scaled, _ = prepare_matrix(feature_matrix)
        kmeans = fit_kmeans(X_scaled, k=4)
        fm_clustered = feature_matrix.copy()
        fm_clustered["cluster"] = kmeans.labels_
        profile = profile_clusters(fm_clustered)
        names = name_segments_from_profile(profile)
        segment_labels = [names[c] for c in kmeans.labels_]
        store_segments(db, feature_matrix["customer_id"], segment_labels, test_cutoff.date())

        print("computing SHAP explanations...")
        shap_values, X_transformed, feature_names = compute_shap_values(churn_model, churn_test[churn_feat_cols])
        store_explanations(
            db, churn_test["customer_id"], shap_values, X_transformed, feature_names, MODEL_VERSION, test_cutoff.date()
        )

        print("done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
