"""Churn model training: baseline -> logistic regression -> random forest
-> XGBoost (guide section 10). All non-baseline models share one
preprocessing pipeline so comparisons isolate the estimator, not
inconsistent preprocessing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL_COLUMNS = ["country", "acquisition_channel", "plan"]


def make_preprocessor(feature_columns: list[str]) -> ColumnTransformer:
    categorical = [c for c in feature_columns if c in CATEGORICAL_COLUMNS]
    numeric = [c for c in feature_columns if c not in CATEGORICAL_COLUMNS]

    numeric_pipeline = Pipeline(
        [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    categorical_pipeline = Pipeline(
        [("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]
    )
    return ColumnTransformer(
        [("numeric", numeric_pipeline, numeric), ("categorical", categorical_pipeline, categorical)]
    )


class BaselineChurnModel:
    """Predicts the training set's overall churn rate for every customer —
    the minimum benchmark any real model must beat (guide section 10,
    "Baseline thinking")."""

    def __init__(self) -> None:
        self.churn_rate_: float | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaselineChurnModel":
        self.churn_rate_ = float(y.mean())
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = np.full(len(X), self.churn_rate_)
        return np.column_stack([1 - p, p])


def train_baseline(X: pd.DataFrame, y: pd.Series) -> BaselineChurnModel:
    return BaselineChurnModel().fit(X, y)


def train_logistic_regression(X: pd.DataFrame, y: pd.Series) -> Pipeline:
    pipeline = Pipeline(
        [
            ("preprocess", make_preprocessor(list(X.columns))),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    return pipeline.fit(X, y)


def train_random_forest(X: pd.DataFrame, y: pd.Series, random_state: int = 42) -> Pipeline:
    pipeline = Pipeline(
        [
            ("preprocess", make_preprocessor(list(X.columns))),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=8,
                    min_samples_leaf=20,
                    class_weight="balanced_subsample",
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    return pipeline.fit(X, y)


def train_xgboost(X: pd.DataFrame, y: pd.Series, random_state: int = 42) -> Pipeline:
    from xgboost import XGBClassifier

    scale_pos_weight = (y == 0).sum() / max((y == 1).sum(), 1)
    pipeline = Pipeline(
        [
            ("preprocess", make_preprocessor(list(X.columns))),
            (
                "model",
                XGBClassifier(
                    n_estimators=300,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    scale_pos_weight=scale_pos_weight,
                    eval_metric="logloss",
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    return pipeline.fit(X, y)


def predict_churn_probability(model, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]
