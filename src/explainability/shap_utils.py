"""SHAP explainability for the churn pipeline (guide section 15). Works
against a sklearn Pipeline("preprocess", "model") where "model" is a
tree-based estimator (XGBoost/RandomForest) — the preprocessor is applied
first so SHAP sees the same post-encoding feature space the model
actually trained on, with real (one-hot) feature names rather than
"feature_12".

Global mean(|SHAP|) tells you what the model leans on overall; the mean
*signed* SHAP direction (not just magnitude) is what tells you whether a
feature pushes toward churn or retention — both are reported, since
"important" and "which direction" are different questions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline


def _transform_and_feature_names(pipeline: Pipeline, X: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    preprocessor = pipeline.named_steps["preprocess"]
    transformed = preprocessor.transform(X)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    feature_names = list(preprocessor.get_feature_names_out())
    return transformed, feature_names


def compute_shap_values(pipeline: Pipeline, X: pd.DataFrame):
    """Returns (shap_values ndarray [n_samples, n_features], X_transformed,
    feature_names) for the fitted tree model inside `pipeline`."""
    import shap

    X_transformed, feature_names = _transform_and_feature_names(pipeline, X)
    model = pipeline.named_steps["model"]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_transformed)
    if isinstance(shap_values, list):  # some estimators return per-class list
        shap_values = shap_values[1]
    return shap_values, X_transformed, feature_names


def global_importance(shap_values: np.ndarray, feature_names: list[str]) -> pd.Series:
    return pd.Series(np.abs(shap_values).mean(axis=0), index=feature_names).sort_values(ascending=False)


def feature_direction(shap_values: np.ndarray, X_transformed: np.ndarray, feature_names: list[str]) -> pd.Series:
    """Correlation between a feature's own value and its own SHAP value.
    Positive = higher feature values push toward churn; negative = higher
    values push toward retention. This is NOT the same as the plain mean
    of SHAP values across customers, which washes out to ~0 for any
    feature with a real but two-sided effect (e.g. recency: low recency
    pushes retention, high recency pushes churn, and a population-wide
    mean cancels those out even though the feature clearly matters)."""
    correlations = {}
    for i, name in enumerate(feature_names):
        col = X_transformed[:, i]
        if np.std(col) == 0:
            correlations[name] = 0.0
        else:
            correlations[name] = float(np.corrcoef(col, shap_values[:, i])[0, 1])
    return pd.Series(correlations).sort_values(ascending=False)


def top_drivers(
    shap_values: np.ndarray, X_transformed: np.ndarray, feature_names: list[str], n: int = 10
) -> tuple[pd.Series, pd.Series]:
    """Among the most important features (by mean |SHAP|), which ones
    have a positive feature-value/SHAP correlation (higher value = more
    churn risk) vs a negative one (higher value = more retention)."""
    importance = global_importance(shap_values, feature_names)
    direction = feature_direction(shap_values, X_transformed, feature_names)
    important_direction = direction.loc[importance.index]
    increases_risk = important_direction[important_direction > 0].head(n)
    decreases_risk = important_direction[important_direction < 0].sort_values().head(n)
    return increases_risk, decreases_risk


def local_explanation(shap_values: np.ndarray, feature_names: list[str], row_index: int, X_transformed: np.ndarray) -> pd.DataFrame:
    """One customer's feature contributions, sorted by |impact|, with the
    actual (transformed) feature value alongside for context."""
    contributions = pd.Series(shap_values[row_index], index=feature_names, name="shap_value")
    values = pd.Series(X_transformed[row_index], index=feature_names, name="feature_value")
    df = pd.concat([values, contributions], axis=1)
    return df.reindex(df["shap_value"].abs().sort_values(ascending=False).index)


def importance_by_segment(shap_values: np.ndarray, feature_names: list[str], segment: pd.Series, top_n: int = 8) -> pd.DataFrame:
    """Mean |SHAP| per feature within each segment value — guide section
    15's "feature importance by segment"."""
    df = pd.DataFrame(np.abs(shap_values), columns=feature_names)
    df["segment"] = segment.reset_index(drop=True).values
    overall_top = global_importance(shap_values, feature_names).head(top_n).index
    return df.groupby("segment")[list(overall_top)].mean()
