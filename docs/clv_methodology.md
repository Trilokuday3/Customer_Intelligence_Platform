# CLV Methodology

Numbers reproduced from `notebooks/06_clv.ipynb` (executed, seed 42).
CLV definition and horizon: `docs/target_definition.md`. Code:
`src/clv/labels.py`, `dataset.py`, `train.py`, `evaluate.py`.

## Label

**Predicted CLV** = net revenue (`completed` orders only) in the 180-day
horizon after the cutoff, for customers active at the cutoff (same
eligibility rule as churn — see `docs/model_card.md`). A churned customer
necessarily has `future_clv = 0` for this horizon; that's a definitional
consequence, not a data error.

**Historical CLV** (descriptive only, never a model input) = cumulative
net revenue through the cutoff.

## Validation strategy

Same time-aware design as churn (`docs/model_card.md`): quarterly
snapshots for train/validation, the true final cutoff held out for test.
CLV uses 4 training cutoffs rather than churn's 5 (the 180-day horizon
needs more runway before `DATA_END`, so one fewer snapshot keeps every
label window fully inside the generated data).

| split | n | mean future_clv |
|---|---|---|
| train | 14,321 | ~293 |
| validation (2025-06-30) | 5,653 | 289 |
| test (held out, 2025-12-31) | 5,097 | 293 |

## Two approaches compared

### 1. Predictive regression (XGBoost, log1p-transformed target)

Reuses the exact feature set built for churn (`src/features`) —
RFM, rolling windows, engagement trend, support/payment behavior — via
`TransformedTargetRegressor(func=log1p, inverse_func=expm1)` to handle
the right-skewed revenue target (skew 1.91, see `docs/eda_report.md`).

| split | MAE | RMSE | Median AE | Spearman rank corr |
|---|---|---|---|---|
| validation | 165.2 | 255.1 | 100.7 | 0.694 |
| test | 168.5 | 257.0 | 104.0 | **0.715** |

High-value capture@10% (test): **50.9%** — of the true top-10%-value
customers, the model's top-10%-predicted list catches about half.

**Known bias**: mean predicted value on test (172.7) is well below mean
actual (292.6). This is the well-known consequence of `log1p`/`expm1`
transforms on skewed targets — `expm1(mean(log1p(y)))` approximates the
*median*, not the mean, of a right-skewed distribution (Jensen's
inequality). The model's *ranking* is still good (that's what Spearman
correlation and decile capture measure), but raw predictions
underestimate aggregate revenue and would need a bias-correction factor
(e.g. Duan's smearing estimator) before being used for a dollar-value
forecast rather than a ranking.

### 2. BG/NBD + Gamma-Gamma (`lifetimes` package)

A purchase-process model: BG/NBD predicts *how many* transactions a
customer will make in the horizon from frequency/recency/tenure alone
(no behavioral features at all); Gamma-Gamma predicts *average order
value* for repeat customers, under an independence-between-frequency-
and-value assumption. Customers with only one historical order
(frequency=0 in `lifetimes`' zero-indexed convention) don't satisfy
Gamma-Gamma's assumptions, so they fall back to the population mean AOV
rather than an unreliable per-customer estimate.

| metric | value |
|---|---|
| MAE | 178.8 |
| RMSE | **240.9** |
| Spearman rank corr | 0.645 |
| High-value capture@10% | 50.7% |
| Mean predicted | 333.3 (actual: 292.6) |

## Which one to use

**Neither dominates** — a genuine trade-off, not a clean win:

- **XGBoost ranks better** (Spearman 0.715 vs 0.645) because it has
  access to engagement/support/payment signal BG/NBD never sees.
- **BG/NBD+Gamma-Gamma is closer to correctly calibrated in aggregate**
  (RMSE 240.9 vs 257.0, mean predicted 333 vs actual 293 — over by ~14%
  — versus XGBoost's mean predicted 173 vs actual 293, under by ~41%).
  It was purpose-built for exactly this calibration property.

**Recommendation**: use XGBoost's *ranking* (who are the highest-value
customers, for prioritization/segmentation) and either apply a bias
correction to its raw values or use BG/NBD+Gamma-Gamma's output when an
actual dollar forecast is needed (e.g. revenue planning). Don't average
the two outputs blindly — they fail in different, understood ways for
different reasons, which is more useful than a single blended number
that hides both.

## Known limitations

- No margin/cost data exists in the synthetic catalog, so CLV here is
  **revenue**, not profit — see `docs/target_definition.md`.
- XGBoost's mean-prediction bias (above) is uncorrected in this pass.
- Single seed; not resampled across multiple generator runs.
