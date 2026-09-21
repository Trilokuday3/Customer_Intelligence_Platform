# Segmentation Report

Numbers reproduced from `notebooks/07_segmentation.ipynb` (executed,
seed 42). Code: `src/segmentation/cluster.py`. Clustering features:
`recency_days`, `frequency`, `monetary`, `order_count_90d`,
`revenue_90d`, `engagement_ratio`, `interval_mean_days`,
`category_breadth`, `tenure_days` (median-imputed, standard-scaled).

## Choosing k

| k | inertia | silhouette | min cluster size |
|---|---|---|---|
| 2 | 49,181 | **0.332** | 2,513 |
| 3 | 41,576 | 0.253 | 1,021 |
| 4 | 35,781 | 0.258 | 921 |
| 5 | 30,411 | 0.268 | 90 |
| 6 | 26,648 | 0.278 | 29 |
| 7 | 23,335 | 0.277 | 29 |
| 8 | 21,157 | 0.274 | 29 |

**Silhouette peaks at k=2**, but per guide section 13 this is checked
alongside usability, not used as the sole criterion — a 2-cluster split
here collapses to a near-trivial "engaged vs. not" cut, and k≥5 produces
a degenerate tiny cluster (min size drops to 90, then 29 — not a usable
business segment). **k=4** is where the inertia elbow visibly flattens
while every resulting cluster stays large enough to target with a
distinct strategy. This trade-off (top silhouette vs. usable structure)
is made explicitly, not silently defaulted to the highest score.

## Cluster profile (k=4, before naming)

| cluster | size | recency (d) | frequency | monetary | engagement ratio | category breadth | tenure (d) | churn rate | future CLV |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 921 | 10.7 | 43.8 | 2,210 | 1.18 | 7.8 | 529 | 4% | 644 |
| 3 | 2,649 | 62.3 | 20.1 | 986 | 0.95 | 7.0 | 532 | 28% | 256 |
| 2 | 2,365 | 363.5 | 5.0 | 243 | 0.02 | 3.2 | 597 | 75% | 36 |
| 1 | 2,065 | 70.4 | 4.5 | 215 | 2.87 | 3.0 | 294 | 36% | 181 |

## Named segments (assigned from the profile above, not before it)

- **Champions** (cluster 0, 921 customers / 11.5%): near-perfect
  recency, highest frequency and revenue by a wide margin, lowest churn
  (4%), highest future value (₹644). Protect this segment — don't
  discount to people who were already going to buy.
- **Steady Regulars** (cluster 3, 2,649 / 33.1%): moderate on every
  metric — the volume base of the business. 28% churn, ₹256 future CLV.
- **Dormant / Lost** (cluster 2, 2,365 / 29.6%): recency of nearly a
  year, almost no recent engagement (ratio 0.02), 75% churn rate, future
  CLV of ₹36. In practice these customers are already gone — a win-back
  campaign is the right lever, not a retention one.
- **New / Developing** (cluster 1, 2,065 / 25.8%): shortest tenure (294
  days vs. 500+ for the others) despite a moderate recency, and the
  *highest* engagement ratio (2.87) — these are recently-active newer
  customers still building purchase habits, not yet showing the longer
  purchase history the other segments have. 36% churn — needs onboarding
  attention, not the same treatment as a lapsing long-tenure customer.

## Hierarchical clustering — a comparison, not the production method

Agglomerative clustering (k=4, same scaled features) run for comparison
per guide 13's ask to "understand hierarchical clustering." **Adjusted
Rand Index vs. K-Means: 0.572** (0 = random agreement, 1 = identical) —
high enough to say the 4-way structure reflects something real in the
data (both algorithms find the same broad divisions), not an artifact of
K-Means' spherical-cluster assumption, while still disagreeing on where
exactly to draw the boundary between adjacent segments (expected, since
the two algorithms optimize different objectives).

## PCA (visualization only)

Clustering ran on the full 9-feature scaled matrix; a 2-component PCA
projection (for visualization only, not used for clustering) captures
65.5% of variance and shows visibly separated clusters along PC1 — see
the notebook for the plot.

## Known limitations

- Segments defined at a single cutoff; not (yet) tracked for drift/
  transition between segments over time (a natural Phase 11 monitoring
  extension).
- `plan`, `country`, `acquisition_channel` were excluded from the
  clustering features (categorical, and `plan`'s circularity with the
  generator's latent activity variable — see `docs/eda_report.md` —
  would have dominated the distance metric). Cross-tabbing segment
  membership against `plan` post-hoc is a natural next check.
