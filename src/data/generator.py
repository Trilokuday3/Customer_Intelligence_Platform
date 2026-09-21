"""Synthetic customer-behavior generator.

Produces customers/products/orders/interactions/support tables that
follow the point-in-time design in config.py: every customer has a
signup date, a latent activity level, and (for most) a simulated
dropout date, so churn/CLV/RFM features computed downstream behave
like a real transactional business rather than i.i.d. noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import config


def _make_rng(seed: int = config.RANDOM_SEED) -> np.random.Generator:
    return np.random.default_rng(seed)


def generate_products(rng: np.random.Generator, n: int = config.N_PRODUCTS) -> pd.DataFrame:
    categories = rng.choice(config.PRODUCT_CATEGORIES, size=n)
    # log-normal prices so a few premium items pull the tail, like real catalogs
    prices = np.round(rng.lognormal(mean=3.2, sigma=0.7, size=n), 2)
    return pd.DataFrame(
        {
            "product_id": [f"P{i:05d}" for i in range(n)],
            "category": categories,
            "price": prices,
        }
    )


def _customer_latent_table(rng: np.random.Generator, n: int = config.N_CUSTOMERS) -> pd.DataFrame:
    days_span = (config.OBSERVATION_CUTOFF - config.DATA_START).days
    # bias signups toward the earlier part of the window so most customers
    # have enough history for a meaningful observation period
    signup_offsets = rng.triangular(0, 0, days_span, size=n).astype(int)
    signup_dates = pd.to_datetime(config.DATA_START) + pd.to_timedelta(signup_offsets, unit="D")

    channel_probs = {
        "organic": 0.30,
        "paid_search": 0.22,
        "social": 0.18,
        "affiliate": 0.10,
        "email": 0.10,
        "referral": 0.10,
    }
    channels = rng.choice(list(channel_probs), size=n, p=list(channel_probs.values()))

    # paid_search / referral customers arrive with slightly higher intent -> higher base rate
    channel_rate_multiplier = (
        pd.Series(channels)
        .map(
            {
                "organic": 1.0,
                "paid_search": 1.25,
                "social": 0.85,
                "affiliate": 0.9,
                "email": 1.05,
                "referral": 1.3,
            }
        )
        .to_numpy()
    )

    base_activity_rate = rng.gamma(shape=2.0, scale=0.018, size=n) * channel_rate_multiplier
    support_friction = rng.beta(a=1.5, b=8.0, size=n)  # most customers low-friction, some high

    plan_score = base_activity_rate + rng.normal(0, 0.01, size=n)
    plan_quantiles = pd.Series(plan_score).rank(pct=True)
    plans = pd.cut(
        plan_quantiles,
        bins=[0, 0.5, 0.85, 1.0],
        labels=["bronze", "silver", "gold"],
        include_lowest=True,
    ).astype(str)

    countries = rng.choice(config.COUNTRIES, size=n, p=[0.45, 0.2, 0.12, 0.08, 0.08, 0.07])

    # simulated "true" lifetime from signup until natural dropout (Weibull hazard);
    # higher activity + lower support friction => longer expected lifetime.
    # Coefficients tuned (see scratchpad tuning run) to land near a 90-day
    # labeled churn rate of ~10% among customers active at the cutoff.
    expected_lifetime_days = 900.0 * (0.4 + base_activity_rate * 14) * (1.0 - 0.4 * support_friction)
    lifetime_days = rng.weibull(a=1.6, size=n) * expected_lifetime_days
    churn_dates = signup_dates + pd.to_timedelta(lifetime_days.astype(int), unit="D")
    data_end = pd.Timestamp(config.DATA_END)
    is_censored = churn_dates > data_end
    churn_dates = churn_dates.where(~is_censored, pd.NaT)

    return pd.DataFrame(
        {
            "customer_id": [f"C{i:06d}" for i in range(n)],
            "signup_date": signup_dates,
            "country": countries,
            "acquisition_channel": channels,
            "plan": plans,
            "base_activity_rate": base_activity_rate,
            "support_friction": support_friction,
            "churn_date": churn_dates,
        }
    )


def _event_days_for_customer(
    rng: np.random.Generator,
    start: pd.Timestamp,
    end: pd.Timestamp,
    daily_rate: float,
    ramp_down_days: int = 0,
) -> np.ndarray:
    """Poisson-process event day-offsets between start/end, with a linear
    ramp-down in rate over the last `ramp_down_days` before `end` when the
    customer actually churns (disengagement precedes churn)."""
    total_days = max(int((end - start).days), 0)
    if total_days == 0 or daily_rate <= 0:
        return np.array([], dtype="int64")

    rate_multiplier = np.ones(total_days)
    if ramp_down_days > 0:
        ramp_start = max(total_days - ramp_down_days, 0)
        ramp_len = total_days - ramp_start
        if ramp_len > 0:
            rate_multiplier[ramp_start:] = np.linspace(1.0, 0.05, ramp_len)

    counts = rng.poisson(daily_rate * rate_multiplier)
    return np.repeat(np.arange(total_days), counts)


def generate_orders(
    rng: np.random.Generator, customers_latent: pd.DataFrame, products: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict] = []
    order_seq = 0
    product_ids = products["product_id"].to_numpy()
    product_prices = products.set_index("product_id")["price"]
    data_end = pd.Timestamp(config.DATA_END)

    for row in customers_latent.itertuples(index=False):
        churned = pd.notna(row.churn_date)
        end = row.churn_date if churned else data_end
        event_days = _event_days_for_customer(
            rng, row.signup_date, end, daily_rate=row.base_activity_rate,
            ramp_down_days=60 if churned else 0,
        )
        if event_days.size == 0:
            continue

        chosen_products = rng.choice(product_ids, size=event_days.size)
        quantities = rng.integers(1, 4, size=event_days.size)
        discounts = rng.choice([0.0, 0.0, 0.0, 0.1, 0.2], size=event_days.size)
        status_roll = rng.random(event_days.size)

        for i, day_offset in enumerate(event_days):
            order_seq += 1
            order_date = row.signup_date + pd.Timedelta(days=int(day_offset), hours=int(rng.integers(0, 24)))
            unit_price = float(product_prices[chosen_products[i]])
            amount = round(unit_price * int(quantities[i]) * (1 - discounts[i]), 2)
            status = "completed"
            if status_roll[i] < 0.02:
                status = "cancelled"
            elif status_roll[i] < 0.06:
                status = "refunded"
            rows.append(
                {
                    "order_id": f"O{order_seq:08d}",
                    "customer_id": row.customer_id,
                    "order_date": order_date,
                    "product_id": chosen_products[i],
                    "quantity": int(quantities[i]),
                    "amount": amount,
                    "discount": float(discounts[i]),
                    "status": status,
                }
            )

    return pd.DataFrame(rows)


def generate_interactions(rng: np.random.Generator, customers_latent: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    seq = 0
    event_types = ["login", "page_view", "add_to_cart", "email_open", "email_click"]
    event_type_probs = [0.25, 0.4, 0.15, 0.15, 0.05]
    channels = ["web", "mobile_app", "email"]
    data_end = pd.Timestamp(config.DATA_END)

    for row in customers_latent.itertuples(index=False):
        churned = pd.notna(row.churn_date)
        end = row.churn_date if churned else data_end
        # interactions happen more often than orders
        event_days = _event_days_for_customer(
            rng, row.signup_date, end, daily_rate=row.base_activity_rate * 6,
            ramp_down_days=90 if churned else 0,
        )
        if event_days.size == 0:
            continue

        types = rng.choice(event_types, size=event_days.size, p=event_type_probs)
        chans = rng.choice(channels, size=event_days.size, p=[0.55, 0.35, 0.10])

        for i, day_offset in enumerate(event_days):
            seq += 1
            event_time = row.signup_date + pd.Timedelta(days=int(day_offset), hours=int(rng.integers(0, 24)))
            rows.append(
                {
                    "interaction_id": f"I{seq:08d}",
                    "customer_id": row.customer_id,
                    "event_time": event_time,
                    "event_type": types[i],
                    "channel": chans[i],
                }
            )

    return pd.DataFrame(rows)


def generate_support_tickets(rng: np.random.Generator, customers_latent: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    seq = 0
    categories = ["billing", "shipping", "product_issue", "cancellation_request", "general"]
    data_end = pd.Timestamp(config.DATA_END)

    for row in customers_latent.itertuples(index=False):
        churned = pd.notna(row.churn_date)
        end = row.churn_date if churned else data_end
        daily_rate = 0.002 + row.support_friction * 0.01
        event_days = _event_days_for_customer(rng, row.signup_date, end, daily_rate=daily_rate)
        if event_days.size == 0:
            continue

        cat_probs = [0.25, 0.25, 0.25, 0.1, 0.15]
        if churned:
            # customers heading toward churn skew toward cancellation-flavored tickets
            cat_probs = [0.2, 0.2, 0.2, 0.25, 0.15]
        cats = rng.choice(categories, size=event_days.size, p=cat_probs)

        for i, day_offset in enumerate(event_days):
            seq += 1
            created_at = row.signup_date + pd.Timedelta(days=int(day_offset), hours=int(rng.integers(0, 24)))
            rows.append(
                {
                    "ticket_id": f"T{seq:07d}",
                    "customer_id": row.customer_id,
                    "created_at": created_at,
                    "category": cats[i],
                }
            )

    return pd.DataFrame(rows)


def to_public_customers(customers_latent: pd.DataFrame) -> pd.DataFrame:
    return customers_latent[["customer_id", "signup_date", "country", "acquisition_channel", "plan"]].copy()


def generate_dataset(
    seed: int = config.RANDOM_SEED,
    n_customers: int = config.N_CUSTOMERS,
    n_products: int = config.N_PRODUCTS,
) -> dict[str, pd.DataFrame]:
    rng = _make_rng(seed)
    customers_latent = _customer_latent_table(rng, n=n_customers)
    products = generate_products(rng, n=n_products)
    orders = generate_orders(rng, customers_latent, products)
    interactions = generate_interactions(rng, customers_latent)
    support = generate_support_tickets(rng, customers_latent)
    customers = to_public_customers(customers_latent)
    return {
        "customers": customers,
        "products": products,
        "orders": orders,
        "interactions": interactions,
        "support": support,
    }
