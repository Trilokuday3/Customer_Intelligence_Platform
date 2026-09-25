from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from churn.calibration import PlattCalibratedModel, fit_platt_calibrator


class _OverconfidentModel:
    """Scores the true risk pushed toward 0/1 (a stand-in for a model that
    ranks well but is overconfident)."""

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        risk = X["risk"].to_numpy()
        logit = 3.0 * np.log(risk / (1 - risk))
        p = 1 / (1 + np.exp(-logit))
        return np.column_stack([1 - p, p])


def _frame(seed: int, n: int = 6000):
    rng = np.random.default_rng(seed)
    risk = rng.uniform(0.05, 0.95, size=n)
    X = pd.DataFrame({"risk": risk})
    y = pd.Series((rng.uniform(size=n) < risk).astype(int))
    return X, y


def test_calibration_reduces_brier_on_unseen_data():
    base = _OverconfidentModel()
    X_cal, y_cal = _frame(0)
    X_test, y_test = _frame(1)
    calibrated = fit_platt_calibrator(base, X_cal, y_cal)

    raw = base.predict_proba(X_test)[:, 1]
    fixed = calibrated.predict_proba(X_test)[:, 1]
    assert brier_score_loss(y_test, fixed) < brier_score_loss(y_test, raw)


def test_calibration_preserves_ranking():
    base = _OverconfidentModel()
    X_cal, y_cal = _frame(0)
    X_test, y_test = _frame(1)
    calibrated = fit_platt_calibrator(base, X_cal, y_cal)

    raw = base.predict_proba(X_test)[:, 1]
    fixed = calibrated.predict_proba(X_test)[:, 1]
    assert roc_auc_score(y_test, fixed) == roc_auc_score(y_test, raw)
    assert np.array_equal(np.argsort(raw, kind="stable"), np.argsort(fixed, kind="stable"))


def test_predict_proba_shape_and_bounds_with_extreme_scores():
    class _Extreme:
        def predict_proba(self, X):
            p = np.array([0.0, 1.0, 0.5])
            return np.column_stack([1 - p, p])

    X = pd.DataFrame({"a": [0, 1, 2]})
    y = pd.Series([0, 1, 1])
    model = fit_platt_calibrator(_Extreme(), X, y)
    out = model.predict_proba(X)
    assert out.shape == (3, 2)
    assert np.isfinite(out).all() and ((out >= 0) & (out <= 1)).all()
    assert isinstance(model, PlattCalibratedModel) and model.base is not None
