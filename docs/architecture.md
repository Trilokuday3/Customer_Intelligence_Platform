# Architecture

## Product shape

Churn prediction + predictive CLV + behavioral segmentation +
customer-360 analytics + cohort/retention analytics + explainability +
transparent retention scenarios, served through a FastAPI backend and a
Next.js dashboard. Not a notebook-only churn project — see
`Customer_Intelligence_Platform_Complete_Project_Guide.docx` for the
full product/module spec this repo implements against.

```
Customer Data -> Data Quality -> EDA -> Feature Engineering
                                            |
                    +----------+-----------+-----------+
                    v          v                       v
                 Churn        CLV                Segmentation
                    +----------+-----------+-----------+
                                v
                          Customer 360
                                v
                    Explainability + Analytics
                                v
                       FastAPI + PostgreSQL
                                v
                        Next.js Dashboard
```

## Repository layout

```
customer-intelligence/
├── src/
│   ├── data/            # schemas, synthetic generator, config (Phase 1 — done)
│   ├── features/        # point-in-time RFM + behavioral features (Phase 4)
│   ├── churn/            # baseline -> logistic -> RF -> XGBoost/LightGBM (Phase 5)
│   ├── clv/               # historical + predictive + BG/NBD/Gamma-Gamma (Phase 6)
│   ├── segmentation/       # RFM rules -> K-Means -> cluster profiling (Phase 7)
│   ├── explainability/      # global/local SHAP (Phase 8)
│   ├── analytics/            # cohorts, retention, scenario simulator (Phase 3/16/17)
│   ├── api/                    # FastAPI routers (Phase 9)
│   └── monitoring/               # data/feature/prediction drift (Phase 11)
├── notebooks/            # 01_data_quality ... 09_scenarios
├── tests/{unit,integration,e2e}
├── frontend/             # Next.js dashboard (Phase 10)
└── docs/
```

Directories are created as the phase that needs them starts, not
speculatively — see the roadmap below for what's actually implemented.

## Data flow (current: Phase 1)

`src/data/generator.py` produces five tables (`customers`, `products`,
`orders`, `interactions`, `support`) that follow a simulated latent
per-customer activity rate and dropout process, so churn/RFM/cohort
signal is present and learnable rather than random. `scripts/generate_data.py`
writes the full dataset to `data/raw/*.parquet` (gitignored — regenerate
locally) and a 200-customer slice to `data/samples/*.csv` (committed,
for quick inspection and CI without regenerating). `tests/unit/test_dq_suite.py`
validates schema conformance, key uniqueness, referential integrity,
value ranges, and date integrity against `src/data/schemas.py`.

## Planned backend (Phase 9+)

```
Data Sources -> Data Pipeline -> Feature Layer
                                    |         \
                                    v          v
                               Analytics   ML Training
                                    |          |
                               PostgreSQL   MLflow -> Model Registry
                                                          |
                                                   FastAPI Inference
                                                          |
                                                    Next.js / React
```

PostgreSQL holds customer/order/prediction data; FastAPI serves both
analytics reads and model inference; MLflow tracks experiments and model
versions; batch/background jobs materialize predictions rather than
computing them synchronously per request.

## Roadmap status

See `Customer_Intelligence_Platform_Complete_Project_Guide.docx` section
33 for the full 12-phase roadmap. Status:

- [x] Phase 1 — Business & Data (churn/CLV definitions, schema, synthetic
      data generator, data dictionary)
- [x] Phase 2 — Data Quality (`notebooks/01_data_quality.ipynb`, on top of
      the `tests/unit/test_dq_suite.py` checks)
- [x] Phase 3 — EDA (`notebooks/02_eda.ipynb`, `notebooks/03_rfm.ipynb`,
      `docs/eda_report.md`; `src/features/rfm.py` — leakage-tested,
      reusable point-in-time RFM)
- [x] Phase 4 — Feature Engineering (`src/features/behavioral.py`: rolling
      windows, engagement trend, purchase intervals, category breadth,
      support/payment behavior — leakage-tested via full-dataset
      future-perturbation test in `tests/unit/test_features.py`)
- [x] Phase 5 — Churn ML (`src/churn/`: baseline → logistic → random
      forest → XGBoost, time-aware quarterly-snapshot validation,
      calibration, segment error analysis — `docs/model_card.md`)
- [x] Phase 6 — CLV (`src/clv/`: predictive XGBoost regression + BG/NBD +
      Gamma-Gamma compared honestly — neither dominates, see
      `docs/clv_methodology.md`)
- [x] Phase 7 — Segmentation (`src/segmentation/cluster.py`: K-Means k=4
      chosen over the silhouette-maximizing k=2 for business usability,
      hierarchical-clustering cross-check, profiled and named from data
      — `docs/segmentation_report.md`)
- [x] Phase 8 — Explainability (`src/explainability/shap_utils.py`: global
      + local SHAP, feature-value/SHAP correlation for direction (a plain
      mean-SHAP washes out for two-sided features like recency),
      importance-by-segment, and a concrete prediction-vs-causation
      example — `docs/explainability_report.md`)
- [x] Phase 9 — Backend (`src/api/`: FastAPI + PostgreSQL, SQLAlchemy
      models, batch-scored predictions/segments/explanations vs.
      on-demand `/predict/*` — verified end-to-end against a real local
      Postgres container, not just SQLite tests — see `docs/api_reference.md`)
- [x] Phase 10 — Frontend (`frontend/`: Next.js 16 + Tailwind v4, all
      guide-20 dashboard pages, verified end-to-end in a real browser
      against the live backend — production build passes clean)
- [x] Phase 11 — MLOps (`src/monitoring/drift.py`: PSI-based feature and
      prediction drift, computed against the training population and the
      prior scoring run respectively; MLflow experiment tracking + model
      registry wired into `scripts/build_backend_data.py`; served via
      `GET /monitoring/drift/{model}` and rendered on the Monitoring page
      — see `docs/monitoring.md`)
- [x] Phase 12 — Portfolio (results-focused `README.md` with real
      screenshots in `docs/screenshots/`; `docs/resume_bullets.md`;
      deployment artifacts — `Dockerfile`, `frontend/Dockerfile`, a
      `docker-compose.yml` `api` profile, `docs/deployment.md` — with no
      actual deployment performed, since that needs an external hosting
      account/domain this repo intentionally hasn't touched)
