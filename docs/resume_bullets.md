# Resume / portfolio bullets (Phase 12)

Draft bullets to adapt, not paste verbatim — trim to whichever role
you're targeting. Every number here is sourced from a doc in this repo
(cited inline) so you can defend it in an interview.

Interview note: the churn figures below (0.735 PR-AUC, 3.0x lift) match the
live dashboard's Model Center, because the deployed model follows the same
select-then-test protocol. Its probabilities are Platt-calibrated on a
held-out snapshot (Brier 0.159 to 0.130, ranking unchanged;
`docs/model_card.md`, "Calibration").

## Project summary (one line)

Built an end-to-end customer intelligence platform — churn prediction,
predictive CLV, behavioral segmentation, and a retention-campaign
simulator — served through a FastAPI/PostgreSQL backend and a Next.js
dashboard, with MLflow tracking and drift monitoring.

## Bullets

- Designed and built a point-in-time-safe ML pipeline (synthetic data
  generator → feature engineering → churn/CLV models) that validates
  across quarterly snapshots instead of a random split, preventing
  identity-level leakage from customers who recur across snapshots
  (`docs/target_definition.md`, `docs/model_card.md`).
- Trained and compared 4 churn models (baseline, logistic regression,
  random forest, XGBoost); champion XGBoost reached **0.735 PR-AUC** and
  **3.0x lift** in the top-decile-targeted population on a held-out
  time-based test set, with calibration and per-segment error analysis
  reported alongside the headline metric (`docs/model_card.md`).
- Built and compared two CLV approaches — an XGBoost regression on
  log-transformed revenue and a BG/NBD + Gamma-Gamma probabilistic
  model — and reported that neither dominates, rather than picking a
  single "winning" number to showcase (`docs/clv_methodology.md`).
- Implemented SHAP-based explainability with a feature-value/SHAP
  correlation method for signed feature *direction*, catching and fixing
  a naive mean-SHAP approach that washed out to ~0 for two-sided
  features like recency (`docs/explainability_report.md`).
- Shipped a FastAPI + PostgreSQL backend serving 15+ endpoints across
  dashboard analytics, customer search/detail, segments, cohorts, and
  on-demand prediction; verified on-demand `/predict/*` scoring matches
  offline batch-precomputed predictions exactly, not just structurally
  (`docs/api_reference.md`).
- Built a Next.js 16 dashboard (8 pages: executive summary, customer
  search/360, segments, cohorts, model center, retention simulator,
  monitoring) verified end-to-end in a real browser against the live
  backend, including a transparent what-if retention-campaign simulator
  that labels its uplift input as an assumption rather than a measured
  effect.
- Added MLOps: MLflow experiment tracking and model registry, plus
  PSI-based feature and prediction drift monitoring that reports
  direction (reference vs. current mean) alongside magnitude so a drift
  alert is diagnosable, not just a red flag (`docs/monitoring.md`).
- Maintained 100+ automated tests (unit + integration, including a
  leakage test that perturbs future rows to confirm point-in-time
  features don't change) across the full pipeline from data generation
  through the API layer.
