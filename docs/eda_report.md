# EDA Report

Every number below is reproduced output from `notebooks/02_eda.ipynb` and
`notebooks/03_rfm.ipynb` (executed, seed 42, 8,000-customer dataset,
cutoff `2025-12-31`) — see `docs/target_definition.md` for the point-in-time
design and `docs/data_dictionary.md` for table definitions.

## Population & activity

- 8,000 total customers; **5,097 (63.7%) active at cutoff** (a completed
  order in the trailing 180 days).
- 523 customers (6.5%) have never placed a qualifying order.

## Revenue distribution

- Historical per-customer revenue (as of cutoff): mean ₹758, median ₹512,
  right-skewed (skew 1.91) — a small number of high-value customers pull
  the mean above the median, as expected for retail spend.
- **Concentration**: top 10% of customers = 33.5% of historical revenue;
  top 20% = 52.8%; top 50% = 85.2%. Meaningful but not extreme
  concentration — there's a real "high-value" segment worth identifying,
  not a single whale dominating everything.
- IQR-based outlier threshold: ₹2,327; 355 customers (4.7%) above it.

## RFM

- Recency: median 59 days since last qualifying order; mean 146 (pulled
  up by the long tail of dormant/lapsed customers).
- Frequency: median 10 orders, mean 14.3, max 132.
- Monetary: median ₹466, mean ₹708.
- Segment sizes (`03_rfm.ipynb`): Champions 1,924 · Loyal 1,685 ·
  Hibernating 1,641 · At Risk 1,191 · Needs Attention 626 · Never
  Purchased 523 · New/Promising 410.
- RFM segments computed **only from historical data** still separate
  forward-looking churn cleanly (checked against the actual 90-day
  outcome, which the segment computation never saw) — this is the core
  justification for RFM as a leading indicator, not just a
  retrospective label.

## Tenure & AOV

- Tenure: median 520 days, mean 490 (customers were seeded with a
  triangular signup distribution skewed toward the start of the window).
- Overall historical average order value: ₹49.36.

## Churn rate & breakdowns

- **Overall churn rate: 28.6%** among the 5,097 active-at-cutoff
  customers — a moderate, learnable imbalance for classification.
- By acquisition channel: affiliate/social highest (~32.7%), referral
  lowest (23.5%) — a ~9pt spread, plausible but not dramatic.
- By plan: bronze 44.8% vs gold 9.7% — a large gap, **but see caveat
  below.**

> **Caveat**: `plan` is derived from the same latent activity-rate
> variable that drives the simulated churn hazard (`src/data/generator.py`),
> so this correlation is partly a construction artifact of the generator,
> not an independently discovered signal. It's a useful sanity check that
> the simulation is internally consistent — don't cite it as a "real"
> business insight if this generator design is reused elsewhere.

## Does engagement trend predict churn? (a real negative + a real positive finding)

- **Negative finding**: raw support-ticket count does **not** separate
  churners from non-churners (`corr = -0.011`, quartile churn rates flat
  at 27–30%) — despite the generator intentionally coupling support
  friction to churn risk. The likely mechanism: customers who churn sooner
  also have less time to accumulate tickets, which offsets their higher
  per-day ticket rate. Left in deliberately rather than tuned away — a
  reminder that an intended signal doesn't automatically show up in a
  naive feature.
- **Positive finding**: a recent-vs-historical engagement ratio (orders
  in the trailing 30 days vs. the customer's own rate over the prior 150
  days) is meaningfully predictive: `corr = -0.131`, and the bottom
  quartile (engagement dropping off) churns at **44.7%** vs **10.5–12.9%**
  for the other three quartiles. This validates the Phase 4 plan to build
  trend/ratio features rather than raw counts.

## Cohort retention

Monthly signup cohorts (`% with a qualifying order, by month since
signup`) settle into a fairly stable band (~45–58%) after month 1, rather
than decaying to zero or staying flat at 100% — i.e., there's a real
"repeat vs. one-time buyer" split baked into the generator, which is what
makes cohort/retention analysis meaningful here rather than trivial.
Full 9x9 table and heatmap in `notebooks/02_eda.ipynb`.

## What this means for Phase 4/5

The dataset has genuine, non-trivial structure: a skewed but not
extreme revenue distribution, a moderate churn rate with real behavioral
correlates (engagement trend, not raw activity counts), and RFM segments
that hold up against forward-looking outcomes. Phase 4 feature
engineering should prioritize **trend/ratio features** (recent vs.
historical activity) over raw counts, given the ticket-count non-finding
above.
