# Churn Model Card

Every number below is reproduced output from `notebooks/04_churn_baseline.ipynb`
and `notebooks/05_churn_models.ipynb` (executed, seed 42). Code lives in
`src/churn/` (`labels.py`, `dataset.py`, `train.py`, `evaluate.py`),
features in `src/features/` — see `docs/target_definition.md` for the
churn definition and `docs/eda_report.md` for the exploratory findings
that motivated the feature set.

## Validation strategy

A single-cutoff dataset can't be split randomly for train/val/test: the
guide explicitly calls for **time-aware validation**, and there's a
subtler reason it matters here — a customer's *identity* persists across
time, so if you computed snapshots at multiple cutoffs and then split
randomly, the same customer could land in both train and validation,
leaking identity-level signal a real deployment would never have (you'd
never train on a customer's Q1 label and validate on the same
customer's Q1 features).

Instead:
- **Training pool**: 5 quarterly snapshots (`2024-09-30`, `2024-12-31`,
  `2025-03-31`, `2025-06-30`, `2025-09-30`), each built independently via
  `src/churn/dataset.build_snapshot` — features strictly `<= cutoff`,
  label from the 90-day window strictly after it.
- **Validation**: the most recent training snapshot (`2025-09-30`),
  used only for model selection.
- **Test**: the final cutoff (`config.OBSERVATION_CUTOFF`, `2025-12-31`)
  — never touched until every model was already trained and the
  champion already chosen on validation.

| split | n | churn rate |
|---|---|---|
| train | 19,974 | 24.0% |
| validation | 5,508 | 28.1% |
| test (held out) | 5,097 | 28.6% |

Churn rate rises across snapshots (21.4% → 28.6%) as the dataset
matures and more customers reach their natural dropout point — a real
effect of the generator's design (`docs/target_definition.md`), not
noise, and part of why a single static split would have understated it.

## Models compared

Baseline (predicts the training churn rate for everyone) → Logistic
Regression (`class_weight="balanced"`) → Random Forest → XGBoost, all
three real models sharing one preprocessing pipeline (median-impute +
scale numeric, most-frequent-impute + one-hot categorical) so
differences reflect the estimator, not inconsistent preprocessing.

### Validation metrics (used for model selection)

| model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | Lift@10% |
|---|---|---|---|---|---|---|---|
| baseline | 0.500 | 0.281 | 0.000 | 0.000 | 0.000 | 0.204 | 0.97 |
| logistic | 0.855 | 0.698 | 0.530 | 0.829 | 0.646 | 0.174 | 2.86 |
| random_forest | 0.861 | 0.723 | 0.556 | 0.799 | 0.656 | 0.155 | 3.02 |
| **xgboost** | **0.861** | **0.726** | 0.548 | 0.809 | 0.653 | 0.158 | 3.03 |

**Champion: XGBoost**, selected on validation PR-AUC (the right metric
here — churn is imbalanced enough that ROC-AUC alone would over-flatter
weak models; PR-AUC and lift are what a retention team would actually
act on).

### Final held-out test metrics (reported once, all models, no cherry-picking)

| model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Brier | Lift@10% |
|---|---|---|---|---|---|---|---|
| baseline | 0.500 | 0.286 | 0.000 | 0.000 | 0.000 | 0.206 | 1.03 |
| logistic | 0.852 | 0.710 | 0.511 | 0.843 | 0.636 | 0.184 | 2.96 |
| random_forest | 0.859 | 0.736 | 0.558 | 0.799 | 0.657 | 0.156 | 3.06 |
| xgboost | 0.861 | 0.735 | 0.550 | 0.812 | 0.656 | 0.159 | 3.01 |

**Honest note**: Random Forest edges out XGBoost on the actual test set
(PR-AUC 0.736 vs 0.735) despite XGBoost winning on validation — a
statistically negligible difference (~0.001), reported rather than
hidden. The model-selection process (pick on validation, confirm on
test) is what's being demonstrated here, not a claim that XGBoost is
definitively better; on this dataset they're effectively tied, both
clearly ahead of logistic regression, and all three are far ahead of
baseline (PR-AUC 0.71–0.74 vs 0.29).

### What is deployed

The deployed model (`scripts/build_backend_data.py`) follows the same protocol
as the tables above: XGBoost trained on the 4 earlier snapshots, then a Platt
calibrator (below) fitted on the 5th (validation) snapshot, which the base
model never saw. Ranking is unchanged by calibration, so the dashboard's Model
Center shows the same PR-AUC 0.735 and lift@10% 3.01 as the test table.

Model metrics on this page are evaluated on labeled history (the 2025-12-31
test set). The dashboard's predictions, segments and drift are scored as of the
newest data day instead, which is later than the training window, so they are
not evaluated against labels.

## Calibration (XGBoost, test set)

The raw model is systematically **overconfident** (it predicts 0.70 where the
observed rate is 0.42). The deployed model therefore applies Platt scaling
(`src/churn/calibration.py`): a logistic regression on the base model's
log-odds, fitted on the validation snapshot. It is monotone, so ROC-AUC,
PR-AUC and lift are unchanged; probabilities become usable as risk estimates.

| predicted (mean), raw | observed | predicted (mean), calibrated | observed |
|---|---|---|---|
| 0.022 | 0.020 | 0.007 | 0.020 |
| 0.067 | 0.018 | 0.024 | 0.018 |
| 0.138 | 0.059 | 0.053 | 0.059 |
| 0.227 | 0.104 | 0.093 | 0.104 |
| 0.330 | 0.173 | 0.149 | 0.173 |
| 0.464 | 0.234 | 0.237 | 0.234 |
| 0.593 | 0.324 | 0.344 | 0.324 |
| 0.700 | 0.417 | 0.460 | 0.417 |
| 0.833 | 0.653 | 0.651 | 0.653 |
| 0.941 | 0.863 | 0.860 | 0.863 |

Brier score improves from 0.159 to **0.130** on the held-out test set. Because
scores are now lower, the fixed 0.5 cut-off means "more likely than not to
churn": precision at 0.5 rises from 0.55 to 0.73 and recall falls from 0.81 to
0.56 (the raw model used class weighting, which inflated its scores). The
dashboard's "high-risk" count uses that same 0.5 cut-off, so it is smaller than
before. The top decile is slightly under-predicted at the low end (0.007 vs
0.020), a limit of a two-parameter curve; isotonic regression would fit it
tighter at the cost of ties in the scores.

## Error analysis by segment (XGBoost, test set)

By plan:

| plan | n | actual churn | predicted positive rate | recall | precision |
|---|---|---|---|---|---|
| silver | 2,029 | 22.1% | 26.4% | 0.699 | 0.586 |
| bronze | 2,027 | 44.8% | 75.0% | 0.880 | 0.526 |
| gold | 1,041 | 9.7% | 9.4% | 0.703 | 0.724 |

By acquisition channel:

| channel | n | actual churn | predicted positive rate | recall | precision |
|---|---|---|---|---|---|
| organic | 1,483 | 29.5% | 44.4% | 0.835 | 0.555 |
| paid_search | 1,173 | 25.6% | 35.3% | 0.797 | 0.577 |
| social | 872 | 32.7% | 51.5% | 0.814 | 0.517 |
| referral | 565 | 23.5% | 30.6% | 0.729 | 0.561 |
| affiliate | 517 | 32.7% | 49.5% | 0.834 | 0.551 |
| email | 487 | 27.7% | 42.1% | 0.822 | 0.541 |

The model over-predicts positive on bronze (75% flagged vs 44.8%
actual) — recall is high (0.88) but at the cost of precision (0.53).
Given `plan`'s circularity caveat in `docs/eda_report.md`, this is
expected: the model has correctly learned that `plan=bronze` is a very
strong signal in this synthetic data, arguably too strong to trust as a
standalone feature if this generator design were reused.

## Top feature importances (XGBoost)

`plan_bronze`, `order_count_60d`, `recency_days`, `order_count_90d`,
`revenue_30d` dominate — consistent with `docs/eda_report.md`'s finding
that recent activity *trend* carries real signal, and consistent with
(and a reminder of) the `plan` circularity caveat above.

## Known limitations

- **`plan` circularity**: carried over from the EDA caveat — `plan` is
  derived from the same latent variable that drives the churn hazard in
  the generator, so its outsized importance here is partly a
  construction artifact.
- **Calibrator is fitted on one snapshot** (the validation snapshot, 5,508 rows), so it inherits that period's churn rate (28.1% vs 28.6% on test).
- **Single random seed**: results aren't averaged over multiple seeds/
  resamples; treat point estimates as approximate, not exact.
- **Synthetic data**: all numbers describe how well these models work on
  *this* generator's data, not a claim about real customer churn.

## Next

CLV modeling (Phase 6), segmentation (Phase 7), and SHAP explainability
(Phase 8) build on this same feature matrix and snapshot design.
