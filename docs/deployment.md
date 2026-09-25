# Deployment (Phase 12)

This documents how each piece *would* deploy and provides the artifacts
to do it (`Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`).
**Nothing here has actually been deployed anywhere external** — no
cloud account, domain, or hosting provider has been touched. Standing
this up on a real host (Render/Railway/Fly for the API + Postgres,
Vercel for the frontend, or any other provider) is a separate,
explicit step for whoever runs this repo, not something performed as
part of building it.

## Run the full stack locally with Docker

```powershell
docker compose --profile api up -d      # postgres + the FastAPI image
python scripts/build_backend_data.py    # trains models, writes ./models (bind-mounted into the api container)
docker compose --profile api restart api   # pick up the freshly written models/
```

**Seeding is one-time.** `build_backend_data.py` seeds the raw tables from
parquet only when `customers` is empty; re-running `generate_data.py` (new
seed) and then the script does not reload the DB. To re-seed from fresh
parquet files, empty the DB first: for local SQLite delete `cip.db`; for
Postgres run `docker compose down -v` (a FULL wipe of Postgres data), then
`docker compose up -d postgres`, then re-run the script.

The API container reads `DATABASE_URL` pointed at the `postgres`
service (set in `docker-compose.yml`) and mounts `./models` read-only —
retraining on the host and restarting the container is the whole
redeploy cycle; the image itself doesn't need rebuilding for a new
model version. Bare `docker compose up` (no `--profile api`) starts
only Postgres, matching how local dev has worked since Phase 9 (run
`uvicorn` directly on the host, against the same database).

Run the frontend against that API with:

```powershell
cd frontend
docker build -t customer-intelligence-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_BASE_URL=http://host.docker.internal:8000 customer-intelligence-frontend
```

`NEXT_PUBLIC_API_BASE_URL` is inlined into the JS bundle at `next build`
time, so it must exist before the build: `frontend/Dockerfile` takes it as
`--build-arg NEXT_PUBLIC_API_BASE_URL=...`, and on Vercel it is a project
environment variable that needs a redeploy when it changes.

## Hosted setup (Neon + Render + Vercel)

Order matters because the URLs depend on each other.

1. **Neon**: create a project, copy the connection string. It must end with
   `?sslmode=require`.
2. **Seed** (your machine): set `DATABASE_URL` to the Neon string, then
   `python scripts/build_backend_data.py`. Seeding is one-time (see above).
   Check the size: `select pg_size_pretty(pg_database_size(current_database()));`
   (free tier is about 0.5 GB).
3. **Bake the models**: copy `models/*.joblib` to `deploy/models/`, commit and
   push. The image must carry the exact models that produced the stored
   predictions, otherwise `POST /predict/*` drifts from the stored scores.
   Repeat this step whenever the database is re-seeded.
4. **Render**: New Blueprint from the GitHub repo (reads `render.yaml`). Enter
   `DATABASE_URL` (Neon string) and a temporary `FRONTEND_ORIGIN`. Note the URL.
5. **Vercel**: import the repo, Root Directory `frontend`, add
   `NEXT_PUBLIC_API_BASE_URL` = the Render URL (no trailing slash), deploy.
6. **Render**: set `FRONTEND_ORIGIN` to the Vercel URL (no trailing slash) and
   redeploy, so CORS allows the dashboard.
7. **GitHub**: add the repository variable `API_URL` (Render URL) so
   `.github/workflows/keep-warm.yml` starts pinging `GET /` every 10 minutes.

The API image installs only `.[api,serve]` (no shap/lightgbm/lifetimes) to fit
Render's 512 MB, and honours Render's `$PORT`.

Checks: `<api>/` and `<api>/monitoring/health` return 200 with row counts;
`POST <api>/predict/churn` equals `GET <api>/customers/{id}`
`churn_probability`; dashboard pages show numbers, not the error state.

Free-tier caveats: Render sleeps after about 15 idle minutes (the keep-warm
ping mitigates, and can be delayed by GitHub); the first request after a long
pause can be slow. The API is public and unauthenticated over synthetic data.

- **MLflow** stays local (`sqlite:///mlflow.db` default, see
  `docs/monitoring.md`); no hosted tracking server.
- No auto-retraining or scheduled batch job: re-seeding and re-baking models
  is a manual runbook step.
