# scripts/stream_producer.py
"""Continuously publish simulated customer activity to Kafka.

Runs on the host (like scripts/generate_data.py). On startup it reads the
current tables from Postgres, estimates per-customer rates, resumes the ID
counters and the simulated clock from what is already stored, then every
`--tick-seconds` of real time samples `tick_seconds * speed` simulated
seconds of activity and publishes it.

Usage:
    docker compose --profile streaming up -d
    .venv/Scripts/python.exe scripts/stream_producer.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api.build_data import raw_tables_seeded, read_raw_tables  # noqa: E402
from api.database import SessionLocal, engine  # noqa: E402
from data import config  # noqa: E402
from streaming.events import (  # noqa: E402
    TOPICS,
    merge_next_ids,
    next_ids_from_frames,
    sample_tick_events,
    sequence_from_id,
    stream_start_time,
)
from streaming.rate_estimation import estimate_customer_rates, restrict_to_history  # noqa: E402

_ID_FIELD = {"orders": "order_id", "interactions": "interaction_id", "support-tickets": "ticket_id"}


def _last_kafka_sequences(bootstrap: str) -> dict[str, int]:
    """Sequence of the last message on each topic (0 if empty/unreadable).

    Messages published but not yet ingested by Spark are invisible in Postgres;
    reading them here keeps a restarted producer from reusing their IDs.
    """
    from kafka import KafkaConsumer, TopicPartition

    result = {topic: 0 for topic in TOPICS}
    try:
        consumer = KafkaConsumer(bootstrap_servers=bootstrap, enable_auto_commit=False)
    except Exception as exc:  # noqa: BLE001
        print(f"warning: cannot read last Kafka messages ({exc}); using database IDs only")
        return result
    try:
        for topic in TOPICS:
            try:
                tp = TopicPartition(topic, 0)
                consumer.assign([tp])
                end = consumer.end_offsets([tp])[tp]
                if end > 0:
                    consumer.seek(tp, end - 1)
                    records = consumer.poll(timeout_ms=5000).get(tp, [])
                    if records:
                        value = json.loads(records[-1].value)
                        result[topic] = sequence_from_id(value[_ID_FIELD[topic]])
            except Exception as exc:  # noqa: BLE001
                print(f"warning: could not read last message of topic {topic} ({exc}); treating as 0")
    finally:
        consumer.close()
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tick-seconds", type=float, default=5.0, help="real seconds between ticks")
    parser.add_argument("--speed", type=float, default=3600.0, help="simulated seconds per real second (3600 = 1 sim hour/sec)")
    parser.add_argument("--bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"))
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        from kafka import KafkaProducer
    except ImportError:
        sys.exit("kafka-python is not installed: pip install -e '.[streaming]'")

    if str(engine.url).startswith("sqlite"):
        print(
            "WARNING: reading a local SQLite database while Spark writes to Postgres "
            "-- is DATABASE_URL not set? Rates and IDs will not match the streamed data."
        )

    db = SessionLocal()
    try:
        if not raw_tables_seeded(db):
            sys.exit("customers table is empty -- run scripts/build_backend_data.py first to seed it")
        tables = read_raw_tables(db)
    finally:
        db.close()

    customers, products = tables["customers"], tables["products"]
    orders, interactions, support = tables["orders"], tables["interactions"], tables["support"]

    sim_clock = stream_start_time(orders, interactions, support)
    # Rates come from the seed history only, so they are identical across restarts
    # (streamed events must not revive dormant customers). The clock and IDs use
    # the FULL frames so streaming resumes after everything already stored.
    history_end = pd.Timestamp(config.DATA_END) + pd.Timedelta(days=1)
    h_orders, h_interactions, h_support = restrict_to_history(orders, interactions, support, history_end)
    rates = estimate_customer_rates(customers, h_orders, h_interactions, h_support, as_of=history_end)
    next_ids = merge_next_ids(next_ids_from_frames(orders, interactions, support), _last_kafka_sequences(args.bootstrap))
    print(f"starting ids (last used): {next_ids}")
    product_prices = dict(zip(products["product_id"], products["price"].astype(float)))
    rng = np.random.default_rng(args.seed)

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    sim_seconds_per_tick = args.tick_seconds * args.speed
    print(
        f"streaming to {args.bootstrap}: {len(rates)} customers, simulated clock starts {sim_clock}, "
        f"{sim_seconds_per_tick / 3600:.1f} simulated hours per {args.tick_seconds:g}s tick. Ctrl+C to stop."
    )

    try:
        while True:
            time.sleep(args.tick_seconds)
            events = sample_tick_events(rates, sim_seconds_per_tick, sim_clock, next_ids, product_prices, rng)
            for topic, messages in events.items():
                for message in messages:
                    producer.send(topic, key=message["customer_id"], value=message)
            producer.flush()
            sim_clock += pd.Timedelta(seconds=sim_seconds_per_tick)
            counts = ", ".join(f"{topic}={len(messages)}" for topic, messages in events.items())
            print(f"[sim {sim_clock:%Y-%m-%d %H:%M}] published {counts}")
    except KeyboardInterrupt:
        print("stopping")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
