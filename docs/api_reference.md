# API Reference

FastAPI + PostgreSQL backend (guide sections 21-22). Code: `src/api/`.
Interactive docs at `/docs` (Swagger UI) once the server is running.

## Running it

```powershell
docker compose up -d postgres          # local Postgres on port 5439 (see .env.example)
python scripts/generate_data.py        # if data/raw/ doesn't exist yet
$env:DATABASE_URL = "postgresql://cip:changeme@localhost:5439/customer_intelligence"   # set BEFORE the build so it seeds Postgres, not SQLite
python scripts/build_backend_data.py   # trains models, seeds DB once, scores, computes explanations
uvicorn api.main:app --app-dir src --reload
```

**Seeding is one-time.** `build_backend_data.py` seeds the raw tables from
parquet only when `customers` is empty; re-running `generate_data.py` (new
seed) and then the script does not reload the DB. To re-seed from fresh
parquet files, empty the DB first: for local SQLite delete `cip.db`; for
Postgres run `docker compose down -v` (a FULL wipe of Postgres data), then
`docker compose up -d postgres`, then re-run the script.

Without `DATABASE_URL` set, the app falls back to a local `cip.db` SQLite
file (gitignored) — fine for a quick look, not for anything beyond that.

## Architecture: batch scoring vs. on-demand

Two different code paths serve predictions, deliberately:

- **`GET` endpoints** (dashboard, customers, segments, analytics, models,
  explanations) read from tables (`predictions`, `customer_segments`,
  `model_runs`, `customer_explanations`) populated **once** by
  `scripts/build_backend_data.py` — a batch job, not a per-request
  computation (guide section 21: "Batch/background jobs for
  predictions"). This is why dashboard metrics are never hard-coded
  (guide 36): they're real, just computed offline and cached, the same
  pattern MLflow's model registry formalizes in Phase 11.
- **`POST /predict/churn` and `POST /predict/clv`** recompute a single
  customer's features live from the DB, as of the same scoring date (see "Scoring date" below),
  and run them through the model loaded at startup. `tests/integration/test_api.py`
  asserts this matches the batch-precomputed value exactly for the same
  customer — a real consistency check, not just "it returns a number."

**Scoring date.** The batch job scores as of the newest data day in the
database (midnight of the latest event), not a fixed cutoff, and stores it as
`prediction_date`. `POST /predict/*` reads that latest `prediction_date` as its
as-of date, so on-demand and batch scores keep matching; before any
predictions exist it falls back to the app's reference cutoff. Pass
`--as-of YYYY-MM-DD` to `build_backend_data.py` to score at a specific date.
The scored population differs by date (about 3,984 customers as of 2026-06-29
on the seed data vs 5,097 at 2025-12-31) because eligibility is "completed
order in the previous 180 days".

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/dashboard/summary` | totals, high-risk count, revenue at risk, segment distribution |
| GET | `/customers` | search/filter (segment, plan, churn/CLV range), sort, paginate |
| GET | `/customers/{id}` | profile + latest prediction + segment + live RFM |
| GET | `/customers/{id}/history` | merged order/interaction/support timeline |
| GET | `/segments` | size + mean churn/CLV per named segment |
| GET | `/segments/{name}` | segment summary + top 10 at-risk members |
| GET | `/analytics/churn?dimension=plan\|acquisition_channel\|country` | churn rate breakdown |
| GET | `/analytics/cohorts` | monthly signup-cohort retention (computed in pandas — see note below) |
| GET | `/models/churn`, `/models/clv` | persisted eval metrics from the last `build_backend_data.py` run |
| POST | `/predict/churn`, `/predict/clv` | on-demand scoring, `{"customer_id": "..."}` |
| GET | `/explanations/{id}` | precomputed top-8 SHAP drivers |
| GET | `/monitoring/health` | DB connectivity, row counts, data freshness |
| GET | `/monitoring/drift/{model_name}` | feature + prediction drift (PSI) — see `docs/monitoring.md` |
| GET | `/` | liveness |

## Design notes / known limitations

- **Cohort retention is computed in pandas, not raw SQL.** Postgres'
  `date_trunc` and SQLite's `strftime` aren't portable to one query, and
  this endpoint has to run identically against both (Postgres in
  production, SQLite in `tests/integration/`). Every other endpoint uses
  real SQL aggregation (`GROUP BY`, joins, `ILIKE` search, pagination).
- **`Prediction` and `CustomerSegment` are wiped and reinserted** on
  every `build_backend_data.py` run rather than versioned. Prediction
  *drift* survives this because the run captures the outgoing table's
  values before overwriting it (see `docs/monitoring.md`) — but there's
  still only ever one live snapshot, not a queryable history of runs.
- The `Base.metadata.create_all()` call in `main.py`'s lifespan always
  targets `api.database.engine` (the default connection), even under
  `tests/integration/`'s dependency-injected test database — harmless
  (it just creates an unused schema in the fallback SQLite file) but
  worth knowing if you see a stray `cip.db` appear; it's gitignored.
- **`load_raw_tables()` deletes tables in FK-safe order** (predictions/
  segments/explanations, then orders/interactions/support, then
  products/customers). This only matters against a real
  foreign-key-enforcing database: SQLite (the test/fallback DB) doesn't
  enforce FKs by default, so the wrong order ran silently for a long
  time and only surfaced as `ForeignKeyViolation` on the *second* run of
  `build_backend_data.py` against a persistent Postgres database.
  `tests/integration/test_build_data_reload.py` turns FK enforcement on
  for a throwaway SQLite engine specifically to catch this in CI.
