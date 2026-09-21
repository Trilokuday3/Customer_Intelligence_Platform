"""Data/feature/prediction drift (Phase 11). Population Stability Index
(PSI) comparing a reference distribution (what a model was trained or
last scored on) against a current one (the latest snapshot) — the same
metric used in production model-monitoring stacks, not a research
metric picked for novelty.

PSI buckets both distributions into the same bin edges (from the
reference sample's quantiles, so bins reflect where the reference data
actually sits) and sums `(current% - reference%) * ln(current% / reference%)`
over bins. Standard industry thresholds (unrelated to this project):
< 0.1 stable, 0.1-0.25 moderate, > 0.25 significant shift worth
investigating. A single PSI number cannot say *why* a feature moved —
pair it with the reference/current means below before acting on it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

STABLE_THRESHOLD = 0.10
MODERATE_THRESHOLD = 0.25
EPS = 1e-6


def population_stability_index(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    reference = pd.to_numeric(reference, errors="coerce").dropna()
    current = pd.to_numeric(current, errors="coerce").dropna()
    if len(reference) < bins or len(current) == 0:
        return 0.0

    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf

    ref_counts = np.histogram(reference, bins=edges)[0].astype(float)
    cur_counts = np.histogram(current, bins=edges)[0].astype(float)

    ref_pct = ref_counts / ref_counts.sum() + EPS
    cur_pct = cur_counts / cur_counts.sum() + EPS

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def drift_severity(psi: float) -> str:
    if psi < STABLE_THRESHOLD:
        return "stable"
    if psi < MODERATE_THRESHOLD:
        return "moderate"
    return "significant"


def compute_feature_drift(reference_df: pd.DataFrame, current_df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """One row per numeric feature: PSI, severity, and both means so a
    human can tell direction, not just magnitude. Non-numeric (categorical)
    feature columns are skipped — PSI as defined here needs an ordering."""
    rows = []
    for col in feature_columns:
        if col not in reference_df.columns or col not in current_df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(reference_df[col]):
            continue
        psi = population_stability_index(reference_df[col], current_df[col])
        rows.append(
            {
                "feature": col,
                "psi": psi,
                "severity": drift_severity(psi),
                "reference_mean": float(pd.to_numeric(reference_df[col], errors="coerce").mean()),
                "current_mean": float(pd.to_numeric(current_df[col], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)


def compute_prediction_drift(reference_scores: pd.Series | np.ndarray, current_scores: pd.Series | np.ndarray) -> dict:
    reference_scores = pd.Series(reference_scores)
    current_scores = pd.Series(current_scores)
    psi = population_stability_index(reference_scores, current_scores)
    return {
        "psi": psi,
        "severity": drift_severity(psi),
        "reference_mean": float(reference_scores.mean()),
        "current_mean": float(current_scores.mean()),
    }
