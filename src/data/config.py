"""Business and generation constants.

The point-in-time design here (cutoff / horizons) is the authoritative
source for docs/target_definition.md — if you change a value here,
update that doc too.
"""

from datetime import date

# --- Point-in-time design (see docs/target_definition.md) ---
DATA_START = date(2024, 1, 1)
OBSERVATION_CUTOFF = date(2025, 12, 31)
CHURN_HORIZON_DAYS = 90
CLV_HORIZON_DAYS = 180
ACTIVE_LOOKBACK_DAYS = 180
DATA_END = date(2026, 6, 30)

# --- Generation scale ---
N_CUSTOMERS = 8000
N_PRODUCTS = 80
RANDOM_SEED = 42

COUNTRIES = ["IN", "US", "GB", "AE", "SG", "AU"]
PRODUCT_CATEGORIES = [
    "electronics",
    "apparel",
    "home",
    "beauty",
    "sports",
    "grocery",
    "books",
    "toys",
]
