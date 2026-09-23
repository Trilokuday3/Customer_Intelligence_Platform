"""Structured Streaming job: Kafka topics -> Postgres raw tables.

One stream per topic. Each micro-batch is collected on the driver (volumes
here are small) and written with psycopg2 `INSERT ... ON CONFLICT DO
NOTHING`, so Spark's at-least-once redelivery after a crash cannot create
duplicate rows. Checkpoints live on a mounted volume so a restart resumes
from the last committed offset.
"""

from __future__ import annotations

import os

import psycopg2
from psycopg2.extras import execute_values
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json

from upsert_sql import TABLES, TableSpec, build_upsert_sql

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
CHECKPOINT_ROOT = os.environ.get("CHECKPOINT_ROOT", "/checkpoints")


def _connect():
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "postgres"),
        port=int(os.environ.get("PG_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "cip"),
        password=os.environ.get("POSTGRES_PASSWORD", "changeme"),
        dbname=os.environ.get("POSTGRES_DB", "customer_intelligence"),
    )


def _make_batch_writer(spec: TableSpec):
    columns = spec.column_names
    sql = build_upsert_sql(spec.table, columns, spec.pk)

    def write(batch_df, batch_id: int) -> None:
        rows = [tuple(row[c] for c in columns) for row in batch_df.select(*columns).collect()]
        if not rows:
            return
        conn = _connect()
        try:
            with conn, conn.cursor() as cur:
                execute_values(cur, sql, rows)
        finally:
            conn.close()
        print(f"[{spec.topic}] batch {batch_id}: upserted {len(rows)} rows into {spec.table}", flush=True)

    return write


def _start_stream(spark: SparkSession, spec: TableSpec):
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", spec.topic)
        .option("startingOffsets", "earliest")
        .load()
    )
    events = (
        raw.select(from_json(col("value").cast("string"), spec.ddl).alias("e"))
        .select("e.*")
        .dropna()  # drop malformed messages: any null column would violate NOT NULL and crash-loop the batch
    )
    return (
        events.writeStream.foreachBatch(_make_batch_writer(spec))
        .option("checkpointLocation", f"{CHECKPOINT_ROOT}/{spec.topic}")
        .trigger(processingTime="5 seconds")
        .start()
    )


def main() -> None:
    spark = SparkSession.builder.appName("cip-stream-ingest").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    for spec in TABLES.values():
        _start_stream(spark, spec)
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
