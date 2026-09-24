# Continuous data streaming (Kafka + Spark)

> Status: verified by hand against Docker on 2026-09-24 (Docker 29.8, 8 cores, 8 GB): the full stack came up, rows landed in Postgres, a producer restart resumed IDs with no duplicates, a `spark-submit` restart (checkpoint replay) added no duplicates, and `build_backend_data.py` kept the streamed rows. Not covered: long runs, broker failure, and the `down`-without-`-v` crash-loop described below (documented from reading, not reproduced), and scoring as of the newest data day after streaming (the stream -> re-run -> scoring date advances chain, and the Postgres timestamps written by Spark), which was only checked offline on SQLite, not yet against Docker/Postgres.

New orders, interactions, and support tickets for existing customers can
stream in continuously: a host-run producer publishes to Kafka, and a Spark
Structured Streaming job upserts them into the Postgres raw tables. Design
and rationale: `docs/superpowers/specs/continuous-data-streaming-design.md`.

```
scripts/stream_producer.py  (host process)
   estimates per-customer rates from history in Postgres,
   Poisson-samples events on a simulated clock
        |
        v
Kafka (single broker, KRaft)   topics: orders, interactions, support-tickets
        |
        v
Spark cluster (spark-master + spark-worker; spark-submit client container)
   spark/stream_ingest_job.py: one stream per topic, foreachBatch upsert
   INSERT ... ON CONFLICT (<pk>) DO NOTHING
        |
        v
Postgres (orders, interactions, support)
        |
        v
scripts/build_backend_data.py  (batch; seeds raw tables only when
   `customers` is empty, then reads all tables from Postgres)
```

## Run it

Prerequisites: Docker Desktop running; the raw tables already seeded by a
prior `python scripts/build_backend_data.py` (the producer exits if
`customers` is empty).

1. Start Postgres, then the streaming stack (first run downloads the Spark
   Kafka/Postgres connector jars via Maven, which takes a few minutes):

   ```powershell
   docker compose up -d postgres
   docker compose --profile streaming up -d --build
   docker compose --profile streaming ps
   docker compose --profile streaming logs spark-submit --tail 40
   ```

   Expect `kafka` healthy, `kafka-init` exited 0 (it creates the three
   topics), `spark-submit` running, and no Python traceback in its log.
   Spark master UI: http://localhost:8080.

2. Start the producer on the host:

   ```powershell
   .venv/Scripts/python.exe -m pip install -e ".[streaming]"
   .venv/Scripts/python.exe scripts/stream_producer.py --seed 7
   ```

   Flags: `--tick-seconds` (real seconds between ticks, default 5),
   `--speed` (simulated seconds per real second, default 3600),
   `--bootstrap` (default `$KAFKA_BOOTSTRAP_SERVERS` or `localhost:29092`),
   `--seed` (RNG seed, default random). It prints one
   `published orders=..., interactions=..., support-tickets=...` line per
   tick; Ctrl+C stops it.

3. Watch the counts climb (run twice, ~30 s apart):

   ```powershell
   docker compose exec postgres psql -U cip -d customer_intelligence -c "select count(*) from orders; select count(*) from interactions; select count(*) from support;"
   ```

4. Re-run `python scripts/build_backend_data.py` whenever fresh scores are
   wanted. It keeps existing (and streamed) rows and reads all tables from
   Postgres. The scoring date printed at the start (`scoring as of ...`) is the newest data day.

   Stop the producer and give Spark a few seconds to drain before re-running
   the batch job; the tables are read one after another while Spark ingests
   each topic separately, so a run during streaming can land on a scoring day
   whose last events have not all arrived, making repeated runs slightly
   non-reproducible.

   The scored population changes gradually as the stream runs (for example a
   few percent by a simulated month, and it increasingly includes customers
   who were dormant in the seed history and receive floor-rate orders);
   expect high-risk counts and drift to move for that reason as well as for
   genuine behavior. Streamed interactions only move the scoring date; the
   current feature set does not use the interactions table, so streamed orders
   and support tickets are what change individual scores.

To reset only the streaming stack (keeping Postgres data), use the narrow
reset in the reset rule below. Do not use `down -v` for this: it also
deletes Postgres data.

## How it works

- **Rates from observable history.** `src/streaming/rate_estimation.py`
  computes per-customer `orders_per_day`, `interactions_per_day`,
  `support_per_day` as historical count / tenure days, with a small floor
  (0.001/day) so nobody goes permanently silent. It does not read the
  generator's hidden `base_activity_rate`.
- **Dormant customers get only the floor rate.** A customer with no order or
  interaction in the 90 days before the end of the seed history (2026-07-01
  00:00) gets only the floor rate (0.001/day): an occasional event, not
  silence. Rates are estimated from the seed history only (streamed rows are
  excluded), so they are identical across producer restarts, and a dormant
  customer does not "wake up" by receiving a floor-rate event.
- **Simulated clock.** History ends 2026-06-30, so wall-clock timestamps
  would leave a fake gap. The producer's clock starts at the later of the
  latest timestamp already in Postgres and the end of the seed history
  (2026-07-01 00:00), so streamed events never fall inside the history the
  rates were estimated from, and advances `tick-seconds * speed`
  simulated seconds per tick (default 5 s x 3600 = 5 simulated hours per
  tick). Each event gets a random timestamp inside its tick.
- **IDs resume from max(Postgres, last Kafka message).** `O`/`I`/`T`
  counters start above the larger of the Postgres maximum and the last
  message on each topic, so restarts are safe even while Spark lags behind
  Kafka. The Kafka read is best-effort (a failure logs a warning and falls
  back to Postgres). Verified live: a restarted producer printed starting ids
  equal to the stored maxima and produced no duplicate keys.
- **At-least-once, idempotent.** Spark checkpointing can redeliver a
  micro-batch after a crash; `ON CONFLICT (<pk>) DO NOTHING` (PKs
  `order_id`, `interaction_id`, `ticket_id`) makes redelivery a no-op.

## Reset rule and operational notes

1. **Clear the Spark checkpoints whenever Kafka is recreated.** Kafka has
   no volume, but Spark checkpoints do (`spark_checkpoints`). After
   `docker compose --profile streaming down` (or anything else that
   recreates the `kafka` container), the next `up` starts with empty topics
   while the checkpoint offsets are ahead of them, and `spark-submit`
   crash-loops with a data-loss error. Recommended streaming-only reset,
   which keeps Postgres data:

   ```powershell
   docker compose --profile streaming rm -sf spark-submit spark-worker spark-master kafka-init kafka
   docker volume rm <project>_spark_checkpoints
   ```

   The project prefix is the folder name lowercased (for example
   `customer_intelligence_platform_spark_checkpoints`); confirm the exact
   name with `docker volume ls`. Then `up -d` again.

   `docker compose --profile streaming down -v` is a FULL wipe: it removes
   all named volumes in the project, including `postgres_data`, so the
   seeded and streamed rows are deleted. Afterwards you must re-run
   `python scripts/build_backend_data.py` to re-seed before the producer can
   start (it exits with "customers table is empty" otherwise).

   `restart`, `stop`, and `start` are safe.
2. **One bad row fails the whole micro-batch.** For example an unknown
   `customer_id` violates the foreign key, the batch raises, and the job
   restart-loops until the checkpoint is reset. Malformed or incomplete rows
   (any null field) are dropped silently by `.dropna()`, so they never reach
   Postgres and are not logged.
3. **Simulated clock and scoring.** Streamed events start at 2026-07-01
   00:00 on a first run (the end of the seed history; the latest seed row is
   2026-06-29 23:00) and resume from the latest stored timestamp after that.
   `build_backend_data.py` scores as of the newest data day (midnight of the
   latest event; override with `--as-of YYYY-MM-DD`), so re-running it after
   streaming moves predictions, segments, SHAP explanations and drift. Model
   training and the Model Center metrics stay on labeled history
   (`OBSERVATION_CUTOFF`, 2025-12-31). At the default speed the scoring date
   advances about 150 simulated days per real hour.

   The scored population differs by date because eligibility is "completed
   order in the previous 180 days": about 3,984 customers are scored as of
   2026-06-29 on the seed data alone, versus 5,097 at 2025-12-31.
4. **Producer is best-effort.** Send failures are not retried (at-least-once
   is on the Spark side), and a broker drop ends the producer loop. Restart
   it; the clock resumes from Postgres and IDs from max(Postgres, last Kafka
   message).
5. **Prediction drift.** `build_backend_data.py` now keeps the
   previous predictions as the drift baseline, so prediction-drift rows appear
   from the second run (the old code deleted predictions before capturing the
   baseline).

## Known limitations

- No new customer signups; only existing customers generate activity.
- No live churn simulation; `churn_date` stays as generated.
- No streaming feature engineering; Spark only ingests. Scoring stays batch.
- Training cutoffs stay fixed. Streaming changes scores, segments and drift
  (scoring is as of the newest data day) but does not retrain on streamed
  data; rolling the training cutoffs forward is a separate design decision.
- No exactly-once delivery; at-least-once plus idempotent upserts is the
  chosen tradeoff.
- Not automated in CI; the Kafka -> Spark -> Postgres path is verified by
  hand against the real stack (see the status note at the top).
- kafka-python 3.x prints a `DeprecationWarning` about the plain-function
  `key_serializer`/`value_serializer`; harmless, and the `>=2.0.3` pin allows
  both major versions.
