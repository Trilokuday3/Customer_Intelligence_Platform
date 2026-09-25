# Customer Intelligence Platform

[![CI](https://github.com/Trilokuday3/Customer_Intelligence_Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Trilokuday3/Customer_Intelligence_Platform/actions/workflows/ci.yml)

Churn prediction, predictive customer lifetime value (CLV), behavioral
segmentation, customer-360 analytics, cohort and retention analytics,
SHAP explainability, and a transparent retention-campaign simulator,
served through a FastAPI + PostgreSQL backend and a Next.js dashboard.
A full product build on synthetic data, not a notebook-only churn project.

## Architecture

```
                         Kafka  <-  stream producer (simulated activity)
                           |
                     Spark Structured Streaming
                           |  idempotent upserts
                           v
Synthetic data  ------>  PostgreSQL (raw tables)
generator (seed)             |
                             v
                    Point-in-time features
                             |
              +--------------+--------------+
              v              v              v
           Churn            CLV        Segmentation
        (XGBoost)    (XGBoost, BG/NBD)   (K-Means)
              +--------------+--------------+
                             v
          Batch job: predictions, segments, SHAP explanations,
          drift report  -->  PostgreSQL     MLflow (runs, registry)
                             |
                             v
                    FastAPI  (reads batch results,
                              plus on-demand /predict/*)
                             |
                             v
                     Next.js dashboard
```

**Data.** A generator simulates five tables (customers, products, orders,
interactions, support tickets) with a latent activity level and a dropout
process, so churn and RFM signal is real and learnable. It seeds
PostgreSQL once. An optional streaming layer then keeps adding new
orders, interactions and tickets for existing customers: a producer
publishes to Kafka, and a Spark Structured Streaming job upserts them
into PostgreSQL with `ON CONFLICT DO NOTHING`, so redelivery never
creates duplicates.

**Features and models.** Every feature and label is computed as of an
explicit cutoff. Models are validated across quarterly snapshots instead
of a random split, because the same customer recurs across snapshots and
a random split would leak identity-level signal. Churn compares a
baseline, logistic regression, random forest and XGBoost. CLV compares an
XGBoost regression with a BG/NBD + Gamma-Gamma probabilistic model.
Segmentation uses K-Means with a hierarchical-clustering cross-check.

**Batch serving.** Dashboard numbers are never computed inside a request.
A batch job (`scripts/build_backend_data.py`) trains the models and
precomputes predictions, segments, SHAP explanations and drift results
into PostgreSQL, and the API reads them back. Only `/predict/*` scores on
demand, and it is verified to match the batch predictions exactly.

**Explainability and monitoring.** SHAP gives global and per-customer
drivers, with feature direction taken from the correlation between
feature value and SHAP value (a plain mean SHAP cancels out for two-sided
features such as recency). PSI drift monitoring covers input features and
prediction distributions and reports reference vs. current means beside
each score so an alert can be diagnosed. MLflow tracks experiments and
the model registry.

**Dashboard.** Next.js 16 with Tailwind: executive summary, customer
search and 360 view, segments, cohorts, model center, a retention
simulator, and monitoring.

**Delivery.** GitHub Actions runs the backend tests and the frontend lint
and build on every push. Docker images and a compose file cover
PostgreSQL, the API, and the optional Kafka/Spark profile. The hosted demo
uses Neon (PostgreSQL), Render (API image with the trained models baked in)
and Vercel (dashboard); setup is in [docs/deployment.md](docs/deployment.md).

Repository layout, data flow and the phase-by-phase status are in
[docs/architecture.md](docs/architecture.md).

## Remaining

- **Hosted demo is a static snapshot.** The dashboard runs on Vercel, the API
  on Render's free tier and the data on Neon, seeded once at the scoring date.
  Kafka and Spark are not hosted, so streaming only runs locally, and the free
  API sleeps when idle (a scheduled ping keeps it warm but can be delayed).
- **Training does not roll forward.** Scoring, segments and drift follow the
  newest data day, so streaming moves the dashboard, but the models are only
  trained and evaluated on labeled history up to a fixed cutoff. Rolling the
  training cutoffs forward as data matures is an open design decision.
- **Streaming scope.** No new customer signups and no live churn
  simulation; Spark only ingests, and feature computation, training and
  scoring stay batch. The producer is best-effort and Kafka/Spark are not
  exercised in CI.
- **No scheduled retraining.** The batch job runs manually; there is no
  scheduler or automatic retrain on drift.
- **Simulator uplift is an assumption.** The retention simulator computes
  campaign economics from live segment data, but the uplift it applies is
  an input, not a measured effect.
- **Synthetic data only.** Results demonstrate the pipeline, not
  performance on a real business's customers.
