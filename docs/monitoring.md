# Monitoring & MLOps (Phase 11)

Two separate concerns, both driven from `scripts/build_backend_data.py`
(guide section 25's "batch/scheduled job", run manually here rather than
on a real scheduler):

1. **Experiment tracking + model registry** — MLflow.
2. **Drift detection** — has the population a model now scores stopped
   looking like the population it was trained (or last scored) on?

Code: `src/monitoring/drift.py` (pure functions, no I/O) and the
`_log_to_mlflow` / drift-wiring in `scripts/build_backend_data.py`.
Served via `GET /monitoring/drift/{model_name}` (`src/api/routers/monitoring.py`)
and rendered on the frontend's Monitoring page.

## Why PSI, not a hypothesis test

The Population Stability Index buckets a reference and a current sample
into the same bins (edges taken from the reference sample's deciles) and
sums `(current% - reference%) * ln(current% / reference%)` over bins. It
was chosen over a KS-test or a t-test because:

- It gives one comparable number per feature regardless of the feature's
  scale, so a dashboard can rank "most-shifted" features across features
  with completely different units (days, currency, counts).
- It doesn't shrink to "significant" on huge samples the way a p-value
  does — with 8,000+ customers a KS-test flags almost any real-world
  distribution difference as significant, which is true but useless for
  triage. PSI's thresholds are about *how much* the distribution moved,
  not whether it moved at all.

Standard thresholds (industry convention, not something tuned for this
project): **PSI < 0.10** stable, **0.10-0.25** moderate, **> 0.25**
significant. A PSI number is a magnitude only — `reference_mean` and
`current_mean` are stored alongside every row precisely so a human can
tell *which direction* a feature moved before deciding whether it
matters (`src/monitoring/drift.py::compute_feature_drift`).

## What's compared against what

Two different drift questions, both computed on every `build_backend_data.py` run:

- **Feature drift**: the model's *training* population (`churn_pool` /
  `clv_pool` — every customer at every historical quarterly cutoff used
  in `CHURN_TRAIN_CUTOFFS` / `CLV_TRAIN_CUTOFFS`) vs. the *current*
  scored population (the scoring snapshot as of the newest data day). This
  answers "does the model still see the kind of customer it learned
  from?" — categorical columns are skipped (PSI as implemented needs an
  ordering; a categorical-drift metric would be a separate chi-squared
  comparison, not implemented here).
- **Prediction drift**: the *previous* run's stored `churn_probability`
  / `predicted_clv` values (read from the `predictions` table **before**
  `store_predictions()` overwrites it) vs. the values just computed.
  This answers "did the model's output distribution move, even if no
  single input feature moved much?" On the very first run ever there is
  no previous run to compare against — the API reports
  `has_prediction_baseline: false` rather than fabricating a zero, and
  the frontend says so explicitly instead of showing a misleading
  "stable."

  The previous run's stored predictions and this run's scoring predictions
  are now from different scoring dates and usually a different set of
  customers (eligibility is "a completed order in the 180 days before the
  scoring date"), so prediction drift measures how the scored population
  moved since the last run, not a change in the model (the models are only
  retrained when the batch job is re-run on the same labeled history). The
  first run after this change compares 5,097 customers scored at 2025-12-31
  with about 3,984 at 2026-06-29 and will likely flag prediction drift as
  significant once.

Both are written to the `drift_reports` table (`src/api/models.py`),
replacing the previous report for that model — the same
wipe-and-reinsert pattern `predictions` and `customer_segments` already
use, for the same reason (single-model demo, not a run history).

## MLflow

`_log_to_mlflow()` in `scripts/build_backend_data.py` logs, per model,
per run: the training cutoffs and feature count as params, the
evaluation metrics (PR-AUC, calibration, MAE, etc. — whatever
`evaluate_churn_model`/`evaluate_clv_model` returned) as metrics, and
the fitted sklearn `Pipeline` itself, registered under
`customer-intelligence-churn` / `customer-intelligence-clv` in the
model registry. Logged with `serialization_format="cloudpickle"`
rather than MLflow 3's new default (`skops`), which refuses to
deserialize an XGBoost estimator inside a sklearn `Pipeline` as an
"untrusted type" — a real constraint hit while building this, not a
hypothetical, and a reasonable trade-off for artifacts that never leave
this machine.

Tracking store defaults to a local SQLite file (`mlflow.db`, gitignored)
with artifacts in `mlruns/` (also gitignored) — no server needed. MLflow
3's pure-filesystem backend is in maintenance mode and rejects new
writes outright, which is why this isn't just a bare `file:./mlruns` URI:

```powershell
python scripts/build_backend_data.py                    # writes to ./mlflow.db + ./mlruns
mlflow ui --backend-store-uri sqlite:///mlflow.db        # inspect runs at http://localhost:5000
```

Set `MLFLOW_TRACKING_URI` (see `.env.example`) to point at a real
`mlflow server` instead — nothing else in `_log_to_mlflow` changes.
Tracking failures (MLflow not installed, tracking server unreachable)
are caught and logged, never fatal: a broken MLOps side-channel
shouldn't block the batch job the live dashboard depends on.

## A real result from this repo's first run

Running `build_backend_data.py` against the generated dataset flags 10
features as "significant" — not a bug, and worth understanding rather
than suppressing. The largest is `tenure_days` (PSI 1.40 on the CLV
model): reference mean 246 days, current mean 453 days. The reference
population pools customers as they looked at *five* historical cutoffs
(`CHURN_TRAIN_CUTOFFS`/`CLV_TRAIN_CUTOFFS`, 2024-09-30 through
2025-09-30) while the current population is the *single* latest
snapshot at `OBSERVATION_CUTOFF` (2025-12-31; the figures below were measured
before scoring moved to the newest data day, so a re-run now reports a later,
different current population). Averaged across cutoffs
that start only ~9 months into `DATA_START`, the reference population
necessarily skews toward newer accounts; by the final cutoff the same
cohort has simply aged. `total_order_count`, `frequency`, `monetary`,
and `category_breadth` show the same pattern for the same reason —
cumulative/tenure-linked features drift mechanically as a growing
customer base ages, which is a real property of *this* dataset's
history, not a churn/CLV signal that changed. This is exactly the kind
of result PSI is supposed to surface for a human to interpret; it is
not, on its own, a reason to retrain.

## What this is not

There's no automated retraining trigger — a "significant" drift result
is surfaced on the Monitoring page for a human to act on, not wired to
kick off `build_backend_data.py` itself. Wiring that up (plus a real
schedule instead of "run manually") is exactly the kind of thing a
`cron`/Airflow/Prefect job would own in a non-demo deployment, and is
called out as out of scope rather than faked.
