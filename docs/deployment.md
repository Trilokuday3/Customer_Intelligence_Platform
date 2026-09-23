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
time (it's a `NEXT_PUBLIC_*` var), so it must be passed as a build arg,
not a runtime `-e`, for a build that will run somewhere other than
`localhost:8000` — the `Dockerfile` above is written for a
same-machine demo; a real deployment needs a `--build-arg` and a
matching `ARG`/`ENV` pair added to the Dockerfile before the API's real
address is known.

## Where each piece would actually go

- **Postgres** — any managed Postgres (Render, Railway, Neon, RDS).
  Point `DATABASE_URL` at it; `docker-compose.yml`'s `postgres` service
  is for local dev only, not a production database.
- **FastAPI** — any container host that can run the root `Dockerfile`
  (Render, Railway, Fly.io). Needs `DATABASE_URL` and `FRONTEND_ORIGIN`
  set, and `models/*.joblib` present in the container — either baked in
  at build time (drop the bind-mount, `COPY models/ models/` in the
  `Dockerfile` instead) or produced by a retraining job with access to
  the same volume/object store.
- **Next.js frontend** — Vercel is the path of least resistance for a
  Next.js App Router project (no Dockerfile needed there at all); the
  `frontend/Dockerfile` here is for deploying it anywhere else a
  container is preferred. Either way it needs `NEXT_PUBLIC_API_BASE_URL`
  set to the FastAPI deployment's public URL at build time.
- **MLflow** (optional) — `docs/monitoring.md` covers the local
  `sqlite:///mlflow.db` default; a real deployment would point
  `MLFLOW_TRACKING_URI` at a hosted MLflow instance or a `mlflow server`
  process with a real database backend, not the local file used here.

## What's intentionally not built

No CI/CD pipeline, no infrastructure-as-code, no auto-deploy on push.
The guide's Phase 12 scope is "deployment" as in *deployable*, not a
maintained production service — this is a portfolio project, and
`docs/architecture.md` / `docs/monitoring.md` already say plainly where
its retraining and monitoring are manual rather than scheduled.
