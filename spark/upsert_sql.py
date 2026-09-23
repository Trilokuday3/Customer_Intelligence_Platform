"""Table specs and SQL for the Spark ingest job. Deliberately free of any
pyspark import so tests/unit/test_stream_contract.py can import it and
check it against the ORM models and the producer's event shape."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    topic: str
    table: str
    pk: str
    columns: tuple[tuple[str, str], ...]  # (column name, Spark SQL type)

    @property
    def column_names(self) -> list[str]:
        return [name for name, _ in self.columns]

    @property
    def ddl(self) -> str:
        return ", ".join(f"{name} {sql_type}" for name, sql_type in self.columns)


# Timestamps stay STRING in Spark (ISO-8601); Postgres casts the literal on insert.
TABLES: dict[str, TableSpec] = {
    "orders": TableSpec(
        topic="orders",
        table="orders",
        pk="order_id",
        columns=(
            ("order_id", "STRING"),
            ("customer_id", "STRING"),
            ("order_date", "STRING"),
            ("product_id", "STRING"),
            ("quantity", "INT"),
            ("amount", "DOUBLE"),
            ("discount", "DOUBLE"),
            ("status", "STRING"),
        ),
    ),
    "interactions": TableSpec(
        topic="interactions",
        table="interactions",
        pk="interaction_id",
        columns=(
            ("interaction_id", "STRING"),
            ("customer_id", "STRING"),
            ("event_time", "STRING"),
            ("event_type", "STRING"),
            ("channel", "STRING"),
        ),
    ),
    "support-tickets": TableSpec(
        topic="support-tickets",
        table="support",
        pk="ticket_id",
        columns=(
            ("ticket_id", "STRING"),
            ("customer_id", "STRING"),
            ("created_at", "STRING"),
            ("category", "STRING"),
        ),
    ),
}


def build_upsert_sql(table: str, columns: list[str], pk: str) -> str:
    """Idempotent insert for psycopg2 execute_values: a redelivered Kafka
    message hits the primary key and is skipped instead of duplicated."""
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s ON CONFLICT ({pk}) DO NOTHING"
