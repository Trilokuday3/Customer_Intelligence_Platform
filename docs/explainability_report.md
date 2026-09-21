# Explainability Report

Numbers reproduced from `notebooks/08_explainability.ipynb` (executed,
seed 42). Code: `src/explainability/shap_utils.py`. Model: the champion
XGBoost churn pipeline from `docs/model_card.md`, retrained on the full
pre-test snapshot pool (model selection already decided in Phase 5) and
explained only against the held-out test cutoff.

## Global importance (top 10, mean |SHAP|)

| feature | importance |
|---|---|
| recency_days | 0.533 |
| plan_bronze | 0.279 |
| tenure_days | 0.239 |
| revenue_30d | 0.236 |
| order_count_90d | 0.184 |
| order_count_60d | 0.173 |
| order_count_180d | 0.139 |
| plan_gold | 0.106 |
| monetary | 0.102 |
| refund_cancel_rate | 0.099 |

Consistent with `docs/model_card.md`'s feature-importance list and
`docs/eda_report.md`'s finding that recent activity carries the real
signal, not raw counts.

## Direction, not just magnitude

A plain mean of SHAP values across all customers isn't a valid way to
find "drivers" — `recency_days` pushes risk up when high and down when
low, so a population-wide mean would wash out toward zero despite it
being the single most important feature. `top_drivers()` instead
correlates each feature's own value with its own SHAP value (see the
docstring in `src/explainability/shap_utils.py`, and the test that
caught this design mistake in `tests/unit/test_explainability.py`).

**Higher value → more churn risk**: `recency_days`, `plan_bronze`,
`cancellation_ticket_count`, `country_AU`, `interval_mean_days`,
`category_breadth`, `frequency`, `tenure_days`.

**Higher value → less churn risk**: `plan_gold`, `country_GB`,
`baseline_order_rate`, `order_count_180d`, `acquisition_channel_referral`,
`order_count_30d`, `non_qualifying_count`, `order_count_60d`.

## Prediction vs. causation — a concrete, not abstract, example

`country_AU` and `country_GB` show up with strong directional
correlations in the lists above. But `src/data/generator.py` never
encodes any country effect on churn — country is assigned independently
of the hazard process that drives who churns. With 6 countries and
roughly 500–3,600 customers per group in the test snapshot, some
spurious correlation is statistically expected by chance alone. A naive
read of the SHAP output would wrongly conclude "AU customers churn
more" — this is the guide's "clear distinction between prediction and
causation" requirement made concrete rather than stated as a caveat with
no example. By contrast, `recency_days`, `plan_bronze`, and the
order-count features ARE causally encoded in the generator (they
directly determine the simulated hazard), so those are the trustworthy
drivers here — the difference between the two groups isn't visible from
SHAP output alone, only from knowing what the generator actually does.

## Local explanations

**Highest-risk customer** (predicted churn probability 99.4%): driven
almost entirely by an extreme `recency_days` z-score (+3.3, i.e. far
longer since their last order than typical), compounded by low recent
order/revenue counts across every window.

**Lowest-risk customer** (predicted churn probability 0.08%): the mirror
image — high monetary value, strongly negative (i.e. recent) recency
z-score, and high order counts across every rolling window. Both
explanations match what a domain expert would expect from the raw
numbers alone, which is the sanity check that matters most before
trusting SHAP output on a real deployment.

## Importance by segment (plan)

| plan | recency_days | (5 more features) |
|---|---|---|
| bronze | 0.448 | |
| silver | 0.533 | |
| gold | 0.699 | |

`recency_days` matters most for `gold` customers — when a normally
frequent, high-value customer goes quiet, that's an unusual and strong
signal. It matters least for `bronze`, where infrequent activity is
closer to that segment's norm, so the same gap says comparatively less.
This is exactly the kind of insight a single global importance ranking
would hide.

## Known limitations

- Explanations describe *this generator's* simulated process, not real
  customer psychology — the country-effect example above is the
  clearest illustration of why that distinction matters.
- SHAP was computed once, on one trained model instance (no averaging
  across retrains/seeds).
