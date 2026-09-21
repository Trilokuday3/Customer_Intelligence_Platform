"""Churn evaluation metrics (guide section 11): threshold-independent
ranking metrics (ROC-AUC, PR-AUC, lift/precision@K), threshold-dependent
metrics (precision/recall/F1), and calibration (Brier score) — plus
segment-level breakdowns for error analysis (section 11.1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k_fraction: float) -> float:
    n = max(int(len(y_score) * k_fraction), 1)
    top_k_idx = np.argsort(y_score)[::-1][:n]
    return float(np.mean(np.asarray(y_true)[top_k_idx]))


def lift_at_k(y_true: np.ndarray, y_score: np.ndarray, k_fraction: float) -> float:
    base_rate = np.mean(y_true)
    if base_rate == 0:
        return float("nan")
    return precision_at_k(y_true, y_score, k_fraction) / base_rate


def evaluate_churn_model(y_true: pd.Series, y_score: np.ndarray, threshold: float = 0.5) -> dict:
    y_true_arr = np.asarray(y_true)
    y_pred = (y_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true_arr, y_pred, labels=[0, 1]).ravel()

    return {
        "roc_auc": roc_auc_score(y_true_arr, y_score),
        "pr_auc": average_precision_score(y_true_arr, y_score),
        "precision": precision_score(y_true_arr, y_pred, zero_division=0),
        "recall": recall_score(y_true_arr, y_pred, zero_division=0),
        "f1": f1_score(y_true_arr, y_pred, zero_division=0),
        "brier_score": brier_score_loss(y_true_arr, y_score),
        "precision_at_10pct": precision_at_k(y_true_arr, y_score, 0.10),
        "lift_at_10pct": lift_at_k(y_true_arr, y_score, 0.10),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
        "base_churn_rate": float(y_true_arr.mean()),
        "threshold": threshold,
    }


def calibration_table(y_true: pd.Series, y_score: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y_true": np.asarray(y_true), "y_score": y_score})
    df["bin"] = pd.qcut(df["y_score"].rank(method="first"), n_bins, labels=False, duplicates="drop")
    table = df.groupby("bin").agg(
        n=("y_true", "count"),
        mean_predicted=("y_score", "mean"),
        observed_rate=("y_true", "mean"),
    )
    return table


def segment_performance(
    y_true: pd.Series, y_score: np.ndarray, segment: pd.Series, threshold: float = 0.5
) -> pd.DataFrame:
    """Error analysis by an arbitrary segment column (tenure bucket, plan,
    channel, ...) — guide section 11.1."""
    df = pd.DataFrame({"y_true": np.asarray(y_true), "y_score": y_score, "segment": segment.values})
    rows = []
    for name, group in df.groupby("segment", observed=True):
        y_pred = (group["y_score"] >= threshold).astype(int)
        rows.append(
            {
                "segment": name,
                "n": len(group),
                "actual_churn_rate": group["y_true"].mean(),
                "predicted_positive_rate": y_pred.mean(),
                "recall": recall_score(group["y_true"], y_pred, zero_division=0),
                "precision": precision_score(group["y_true"], y_pred, zero_division=0),
            }
        )
    return pd.DataFrame(rows).sort_values("n", ascending=False)
