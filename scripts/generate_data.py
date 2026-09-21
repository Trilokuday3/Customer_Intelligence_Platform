"""Generate the synthetic dataset and write data/raw (parquet, gitignored)
plus a small data/samples (csv, committed) for quick inspection/tests.

Usage:
    .venv/Scripts/python.exe scripts/generate_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data.generator import generate_dataset  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
SAMPLES_DIR = ROOT / "data" / "samples"
SAMPLE_CUSTOMERS = 200


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset()

    for name, df in dataset.items():
        df.to_parquet(RAW_DIR / f"{name}.parquet", index=False)
        print(f"wrote {name}: {len(df):,} rows -> data/raw/{name}.parquet")

    sample_customer_ids = set(dataset["customers"]["customer_id"].head(SAMPLE_CUSTOMERS))
    dataset["customers"].head(SAMPLE_CUSTOMERS).to_csv(SAMPLES_DIR / "customers.csv", index=False)
    dataset["products"].to_csv(SAMPLES_DIR / "products.csv", index=False)
    dataset["orders"][dataset["orders"]["customer_id"].isin(sample_customer_ids)].to_csv(
        SAMPLES_DIR / "orders.csv", index=False
    )
    dataset["interactions"][dataset["interactions"]["customer_id"].isin(sample_customer_ids)].to_csv(
        SAMPLES_DIR / "interactions.csv", index=False
    )
    dataset["support"][dataset["support"]["customer_id"].isin(sample_customer_ids)].to_csv(
        SAMPLES_DIR / "support.csv", index=False
    )
    print(f"wrote {SAMPLE_CUSTOMERS}-customer sample -> data/samples/")


if __name__ == "__main__":
    main()
