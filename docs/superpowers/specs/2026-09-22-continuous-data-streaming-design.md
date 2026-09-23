# Continuous data streaming (Kafka + Spark ingestion)

## Goal

Today, the dataset is generated once (`scripts/generate_data.py`) and loaded
into Postgres once per `build_backend_data.py` run, which also *wipes and
reloads* the raw tables every time. There is no ongoing activity — the
dataset is static between runs.

This adds a real streaming ingestion layer so new customer activity
(orders, interactions, support tickets) keeps arriving continuously for
existing customers, on top of the historical data `generate_data.py`
already seeds. `scripts/build_backend_data.py` keeps its current job
(train/score/drift) but now runs against a live, growing dataset instead
of a static snapshot repeated.

## Non-goals

- No new customer signups during streaming — only existing customers
  generate new activity.
- No dynamic/live churn simulation — `churn_date` stays exactly what
  `generate_data.py` assigned at history-generation time. Churn/CLV
  labeling logic is untouched by this change.
- No streaming feature engineering — Spark's job is ingestion only
  (Kafka → Postgres raw tables). Feature computation, model
  training/scoring, and drift stay batch, in `build_backend_data.py`,
  unchanged in *logic* (only in when they're run and what they're run
  against).
- No exactly-once delivery guarantee — at-least-once + idempotent
  upserts (below) is the chosen tradeoff, not a gap to close later.

## Architecture

```
scripts/stream_producer.py (host process, python -m venv, like the
        │  existing scripts/generate_data.py)
        │
        │  On startup: loads the raw tables from Postgres
        │  (read_raw_tables), estimates a per-customer per-event-type
        │  daily rate (src/streaming/rate_estimation.py), initializes ID
        │  counters from MAX(order_id) / MAX(interaction_id) /
        │  MAX(ticket_id), and starts a simulated clock at the latest
        │  timestamp already stored.
        │
        │  Loop forever: sleep(tick_seconds), Poisson-sample how many
        │  events of each type each customer generates in the simulated
        │  tick (tick_seconds * speed) (src/streaming/events.py),
        │  publish each as a JSON message.
        ▼
   Kafka (single broker, KRaft mode — no Zookeeper)
   topics: orders, interactions, support-tickets
        ▼
Spark cluster (docker-compose: spark-master + spark-worker)
        │  spark/stream_ingest_job.py, submitted via a spark-submit
        │  client container. One readStream per topic, JSON-decoded
        │  against an explicit schema, foreachBatch per micro-batch:
        │  collect() to plain tuples, upsert into Postgres via psycopg2
        │  (INSERT ... ON CONFLICT (<pk>) DO NOTHING).
        ▼
   Postgres (customers, orders, interactions, support — schema
   unchanged)
        ▼
scripts/build_backend_data.py (unchanged logic; run manually/whenever
   fresh scores are wanted) — now seeds raw tables only once (skips
   reload if `customers` already has rows), then reads all raw tables
   from Postgres (read_raw_tables) so streamed rows are included in
   feature computation, scoring, and drift.
```

## Components

### `src/streaming/rate_estimation.py` (new)

Pure functions, unit-tested, no Kafka/Spark/DB dependency at the
function level (callers pass in already-queried DataFrames):

- `estimate_customer_rates(customers, orders, interactions, support, as_of) -> pd.DataFrame`
  — for each customer, computes `orders_per_day`, `interactions_per_day`,
  `support_per_day` as `historical_count / max(tenure_days, 1)`, with a
  small floor so customers with zero history still get a nonzero (very
  low) rate rather than going permanently silent. Customers with no
  order or interaction in the 90 days before `as_of` (dormant/churned)
  get only the floor rate (an occasional event, not silence). The producer
  passes seed history only (`restrict_to_history`) so rates are stable across
  restarts.

Deliberately does *not* read `generator.py`'s hidden
`base_activity_rate` — that's simulation ground truth a real system
wouldn't have access to. Estimating from observable history keeps the
producer honest to what a real ingestion system could actually know.

### `src/streaming/events.py` (new)

Pure functions, unit-tested:

- `sample_tick_events(rates, tick_seconds, tick_start, next_ids, product_prices, rng) -> dict[str, list[dict]]`
  — `tick_seconds` is *simulated* time, `tick_start` the simulated clock
  and `product_prices` the lookup for order `amount`. For each customer
  and event type, Poisson-samples a count for this
  tick (`rate_per_day * tick_seconds / 86400`), and for each sampled
  event builds a JSON-serializable dict matching the existing table
  columns (reusing `generator.py`'s category/status/channel/discount
  distributions so new activity looks like the same simulated
  business). `next_ids` is a small in-memory counter dict the caller
  owns and this function increments, mirroring the `O{seq:08d}` /
  `I{seq:08d}` / `T{seq:07d}` ID formats already in use. Also
  `next_ids_from_frames` and `stream_start_time`. Event timestamps are
  on the simulated clock: history ends at 2026-06-30, so wall-clock
  timestamps would leave a fake gap; the producer starts the clock at
  the latest stored timestamp and advances it `tick_seconds * speed`
  per tick (default speed 3600).

### `scripts/stream_producer.py` (new)

Thin entrypoint, run on the host exactly like `scripts/generate_data.py`
(`python scripts/stream_producer.py`), not containerized:

1. Connect to Postgres and load the raw tables via `read_raw_tables`.
2. Call `estimate_customer_rates`, seed `next_ids` from `MAX(...)` per
   table, and start the simulated clock at `stream_start_time`.
3. Loop: `sleep(--tick-seconds)` (default 5s), call `sample_tick_events`
   (simulated tick = `tick_seconds * --speed`, default speed 3600),
   publish each event as a JSON message (key = `customer_id`) to the
   matching Kafka topic via `kafka-python`'s `KafkaProducer`.
4. Log a one-line summary per tick (counts published per topic) so a
   demo/screen-recording shows visible activity.

### `spark/stream_ingest_job.py` (new)

PySpark Structured Streaming application:

- One `readStream` per topic (`orders`, `interactions`,
  `support-tickets`) from Kafka, `from_json` against an explicit
  `StructType` matching each table's columns.
- Rows with any null field (malformed or incomplete) are dropped with `.dropna()`.
- One `writeStream` per topic with `foreachBatch`, `collect()`ing each
  micro-batch to plain tuples (numpy scalars are not adapted by
  psycopg2, and it avoids a pandas dependency in the Spark image) and
  upserting into Postgres via psycopg2
  `execute_values(..., "INSERT INTO ... VALUES %s ON CONFLICT (<pk>) DO NOTHING")`,
  where `<pk>` is `order_id`, `interaction_id`, or `ticket_id`. The
  table names are `orders`, `interactions`, and `support`.
- Checkpoints written to a mounted volume (`/checkpoints/<topic>`) so
  restarts resume from the last committed offset instead of
  reprocessing the whole topic.
- `spark.streams.awaitAnyTermination()` at the end to keep the
  application alive.

### `spark/Dockerfile` (new)

Thin image for the `spark-submit` client container: based on
`apache/spark:3.5.1-python3` (same image as `spark-master`/`spark-worker`
for binary compatibility), copies in `spark/stream_ingest_job.py`, and
its command runs:

```
spark-submit --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.3 \
  /app/stream_ingest_job.py
```

`--packages` downloads via Maven on first run; the ivy cache is a named
volume so restarts don't re-download.

### `docker-compose.yml` changes

New services, all under a `streaming` profile (`docker compose
--profile streaming up -d`) so the default `docker compose up -d
postgres` workflow is unaffected:

- `kafka` — `apache/kafka:3.7.0`, KRaft combined mode (broker +
  controller, no Zookeeper), internal listener `kafka:9092` for
  other containers, external listener mapped to `localhost:29092` for
  the host-run producer.
- `kafka-init` — one-shot service that creates the three topics before
  Spark subscribes (no reliance on auto-creation).
- `spark-master`, `spark-worker` — `apache/spark:3.5.1-python3`, standard
  master/worker config, one worker (sufficient for this data volume).
- `spark-submit` — built from `spark/Dockerfile`, `depends_on: [kafka-init,
  postgres, spark-master, spark-worker]`, `restart: unless-stopped` (it's a
  long-running streaming query, not a one-shot job).

### `scripts/build_backend_data.py` change (existing file)

The only change to already-existing logic. Currently calls
`build_data.load_raw_tables(...)` unconditionally every run, which
wipes and reloads `customers`/`products`/`orders`/`interactions`/
`support` from the parquet files every time — that would
destroy whatever Kafka/Spark has streamed in since the last run.

New behavior: `seed_raw_tables_if_empty` checks whether `customers`
already has rows before calling `load_raw_tables`. Empty → full seed
load from parquet (today's behavior, once). Non-empty → skip it. Either
way the script then reads all tables from Postgres with `read_raw_tables`
(the original historical data plus everything streamed in since), since
the training code previously consumed the parquet DataFrames directly
and would have ignored streamed rows.

## Error handling / delivery semantics

Kafka + Spark Structured Streaming checkpointing is at-least-once: a
crash between processing a micro-batch and committing its checkpoint
can cause that batch to be reprocessed on restart. The `ON CONFLICT
(<pk>) DO NOTHING` upsert makes redelivery a no-op instead of a
duplicate row, so this is an accepted, handled tradeoff rather than an
open risk.

## Testing

- `src/streaming/rate_estimation.py` and `src/streaming/events.py`:
  normal `pytest` unit tests under `tests/unit/`, seeded RNG,
  no Kafka/Spark/Docker — same pattern as every other `src/` module.
- The Kafka → Spark → Postgres path itself: verified manually against
  the real `docker compose --profile streaming up -d` stack (confirm
  Postgres row counts climb over time), the same "verify against real
  infra, not just mocks" approach that caught the FK-delete-order bug
  earlier in this project. Not automated in CI — bringing up a
  Kafka+Spark cluster in CI for this is disproportionate to the value
  for a portfolio project.

## New dependencies

- `pyproject.toml`: new optional-dependency group `streaming = ["kafka-python>=2.0.3"]`
  (only needed by `scripts/stream_producer.py`; the pure `src/streaming/*`
  modules need nothing beyond pandas/numpy, already present).
- Spark's dependencies (`pyspark`, Kafka/Postgres connector jars) live
  entirely inside the `spark/` Docker images, not in the project's
  Python venv.

## Rollout / manual verification steps

1. `docker compose --profile streaming up -d` (brings up kafka, kafka-init,
   spark-master, spark-worker, spark-submit; postgres must already be
   up from the normal `docker compose up -d postgres`).
2. `python scripts/stream_producer.py` on the host.
3. Watch Postgres: `SELECT COUNT(*) FROM orders;` climbing over
   successive checks confirms the full path works end to end.
4. Re-run `python scripts/build_backend_data.py` at any point to
   rescore/retrain against however much new data has accumulated, and
   see the drift report reflect real (not repeated-identical) drift.
   (Amended: see Implementation notes; scoring stays at the fixed
   `OBSERVATION_CUTOFF`, so streamed rows do not move drift yet.)

## Implementation notes

Deviations found while reading the code; the sections above already reflect
them. Runbook: `docs/streaming.md`.

- Real key/table names: PKs are `order_id`, `interaction_id`, `ticket_id`
  (not `id`); the support table is `support` (topic stays `support-tickets`).
- `sample_tick_events` also takes `tick_start` and `product_prices`.
- Events use a simulated clock (starts at the latest stored timestamp,
  advances `tick_seconds * speed`, default 3600) because history ends
  2026-06-30.
- Dormant customers (no order/interaction in the last 90 days) get only the
  floor rate (0.001/day, an occasional event, not silence); a plain count /
  tenure rate would revive churned customers. Rates use seed history only
  (`restrict_to_history`), so they are identical across producer restarts.
- Producer IDs resume from max(Postgres, last message on each Kafka topic) so
  restarts are safe while Spark lags. The Kafka read is unverified live.
- Streamed events start at the later of the latest stored timestamp
  (2026-06-29 23:00 for the seed data) and the end of the seed history
  (2026-07-01 00:00). Scoring stays at `OBSERVATION_CUTOFF` (2025-12-31) and
  label horizons end before that, so scores are unaffected.
- Prediction-drift rows now appear from the second `build_backend_data.py`
  run: the previous-predictions baseline survives (old code deleted
  predictions first).
- `build_backend_data.py` trains from DataFrames, so it now reads tables from
  Postgres (`read_raw_tables`) and seeds from parquet only when `customers` is
  empty (`seed_raw_tables_if_empty`, alongside `raw_tables_seeded`).
- Spark image is `apache/spark:3.5.1-python3` rather than Bitnami.
- The job uses `collect()` rather than `toPandas()`, and `.dropna()` drops
  malformed rows.
- Added a `kafka-init` service to create topics.
- Scoring cutoff stays at `OBSERVATION_CUTOFF` (2025-12-31), so streamed rows
  (dated from 2026-07-01) do not change features or drift yet.
- Not yet verified: the live Kafka -> Spark -> Postgres run.
