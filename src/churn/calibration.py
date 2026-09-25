"""Post-hoc probability calibration for the churn model (Platt scaling).

The boosted model ranks customers well but is overconfident in the middle
of the range (docs/model_card.md, "Calibration"). Platt scaling fits a
logistic regression on the base model's log-odds using snapshots the base
model never trained on. It is monotone, so ranking metrics (ROC-AUC, PR-AUC,
lift) are unchanged; only the probabilities move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

_EPS = 1e-6


def _log_odds(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1 - _EPS)
    return np.log(p / (1 - p)).reshape(-1, 1)


class PlattCalibratedModel:
    """A fitted base classifier plus a Platt calibrator, used like the base
    (`predict_proba`). `base` stays reachable for tools that need the raw
    estimator, such as SHAP."""

    def __init__(self, base, calibrator: LogisticRegression) -> None:
        self.base = base
        self.calibrator = calibrator

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.base.predict_proba(X)[:, 1]
        p = self.calibrator.predict_proba(_log_odds(raw))[:, 1]
        return np.column_stack([1 - p, p])


def fit_platt_calibrator(base, X_calibration: pd.DataFrame, y_calibration: pd.Series) -> PlattCalibratedModel:
    """`X_calibration`/`y_calibration` must be held out from the base model's
    training data, otherwise the calibrator learns the base model's
    in-sample overconfidence instead of correcting it."""
    raw = base.predict_proba(X_calibration)[:, 1]
    calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(_log_odds(raw), np.asarray(y_calibration))
    return PlattCalibratedModel(base, calibrator)
