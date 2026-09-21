"""CLV evaluation (guide section 12.3): error metrics plus ranking
quality — a churn-style AUC doesn't apply to a regression target, so
"can we find the high-value customers" is measured via decile lift and
rank correlation instead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error


def evaluate_clv_model(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    y_true_arr = np.asarray(y_true)
    return {
        "mae": mean_absolute_error(y_true_arr, y_pred),
        "rmse": mean_squared_error(y_true_arr, y_pred) ** 0.5,
        "median_ae": median_absolute_error(y_true_arr, y_pred),
        "spearman_rank_corr": spearmanr(y_true_arr, y_pred).correlation,
        "mean_actual": float(y_true_arr.mean()),
        "mean_predicted": float(np.mean(y_pred)),
    }


def decile_table(y_true: pd.Series, y_pred: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Predicted-vs-actual value by decile of PREDICTED value (guide
    12.3) — reveals whether the model's own top-ranked customers are
    actually the highest-value ones, not just whether errors are small
    on average."""
    df = pd.DataFrame({"y_true": np.asarray(y_true), "y_pred": y_pred})
    df["decile"] = pd.qcut(df["y_pred"].rank(method="first"), n_bins, labels=False, duplicates="drop")
    table = df.groupby("decile").agg(
        n=("y_true", "count"),
        mean_predicted=("y_pred", "mean"),
        mean_actual=("y_true", "mean"),
    )
    return table.sort_index(ascending=False)


def high_value_capture_at_k(y_true: pd.Series, y_pred: np.ndarray, k_fraction: float = 0.1) -> float:
    """Of the top-k% actual-value customers, what fraction does the model's
    top-k% predicted ranking capture? A ranking-quality check independent
    of absolute error scale."""
    n = max(int(len(y_pred) * k_fraction), 1)
    actual_top = set(np.argsort(np.asarray(y_true))[::-1][:n])
    predicted_top = set(np.argsort(y_pred)[::-1][:n])
    return len(actual_top & predicted_top) / n
