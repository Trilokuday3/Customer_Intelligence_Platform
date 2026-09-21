"""CLV modeling: predictive regression (shared feature pipeline, XGBoost,
log1p-transformed target given the right-skewed revenue distribution —
see docs/eda_report.md) and BG/NBD + Gamma-Gamma (guide section 12.1's
probabilistic alternative, via the `lifetimes` package)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import Pipeline

from churn.train import make_preprocessor

QUALIFYING_STATUS = "completed"


def train_predictive_clv(X: pd.DataFrame, y: pd.Series, random_state: int = 42) -> Pipeline:
    from xgboost import XGBRegressor

    regressor = TransformedTargetRegressor(
        regressor=XGBRegressor(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=random_state,
            n_jobs=-1,
        ),
        func=np.log1p,
        inverse_func=np.expm1,
    )
    pipeline = Pipeline([("preprocess", make_preprocessor(list(X.columns))), ("model", regressor)])
    return pipeline.fit(X, y)


def predict_clv(model, X: pd.DataFrame) -> np.ndarray:
    return np.clip(model.predict(X), a_min=0, a_max=None)


def fit_bg_nbd_gamma_gamma(orders: pd.DataFrame, as_of: pd.Timestamp):
    """Returns (bgf, ggf, calibration_summary). calibration_summary has
    columns [frequency, recency, T, monetary_value] indexed by
    customer_id, as `lifetimes` expects. Gamma-Gamma is fit only on
    repeat customers (frequency > 0) per its independence assumption."""
    from lifetimes import BetaGeoFitter, GammaGammaFitter
    from lifetimes.utils import summary_data_from_transaction_data

    as_of = pd.Timestamp(as_of)
    qualifying = orders[(orders["status"] == QUALIFYING_STATUS) & (orders["order_date"] <= as_of)]

    summary = summary_data_from_transaction_data(
        qualifying,
        customer_id_col="customer_id",
        datetime_col="order_date",
        monetary_value_col="amount",
        observation_period_end=as_of,
    )

    bgf = BetaGeoFitter(penalizer_coef=0.01)
    bgf.fit(summary["frequency"], summary["recency"], summary["T"])

    repeat_customers = summary[summary["frequency"] > 0]
    ggf = GammaGammaFitter(penalizer_coef=0.01)
    ggf.fit(repeat_customers["frequency"], repeat_customers["monetary_value"])

    return bgf, ggf, summary


def predict_clv_bg_nbd_gamma_gamma(bgf, ggf, summary: pd.DataFrame, horizon_days: int, fallback_value: float) -> pd.Series:
    """Expected transactions in the horizon x expected average order
    value. Customers with frequency == 0 (a single historical order)
    violate Gamma-Gamma's assumption, so their monetary value is a fixed
    population fallback (mean AOV) rather than an unreliable per-customer
    estimate."""
    expected_transactions = bgf.predict(horizon_days, summary["frequency"], summary["recency"], summary["T"])

    expected_value = pd.Series(fallback_value, index=summary.index)
    repeat_mask = summary["frequency"] > 0
    expected_value.loc[repeat_mask] = ggf.conditional_expected_average_profit(
        summary.loc[repeat_mask, "frequency"], summary.loc[repeat_mask, "monetary_value"]
    )

    return (expected_transactions * expected_value).rename("predicted_clv")
