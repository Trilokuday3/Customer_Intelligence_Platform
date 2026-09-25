import { ApiError, getModelMetrics } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import type { ModelMetrics } from "@/lib/types";

const METRIC_LABELS: Record<string, string> = {
  roc_auc: "ROC-AUC",
  pr_auc: "PR-AUC",
  precision: "Precision",
  recall: "Recall",
  f1: "F1",
  brier_score: "Brier score",
  precision_at_10pct: "Precision @10%",
  lift_at_10pct: "Lift @10%",
  base_churn_rate: "Base churn rate",
  mae: "MAE",
  rmse: "RMSE",
  median_ae: "Median AE",
  spearman_rank_corr: "Spearman rank corr.",
  mean_actual: "Mean actual",
  mean_predicted: "Mean predicted",
};

const HEADLINE: Record<"churn" | "clv", string[]> = {
  churn: ["pr_auc", "roc_auc", "lift_at_10pct"],
  clv: ["mae", "spearman_rank_corr", "rmse"],
};

async function safeGetModelMetrics(name: "churn" | "clv"): Promise<ModelMetrics | null> {
  try {
    return await getModelMetrics(name);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export default async function ModelCenterPage() {
  const [churn, clv] = await Promise.all([safeGetModelMetrics("churn"), safeGetModelMetrics("clv")]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Model Center"
        description="How well each model performs on data it never saw during training. Metrics are computed once by the batch job and stored, not recalculated per request."
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ModelCard title="Churn model" kind="churn" model={churn} />
        <ModelCard title="CLV model" kind="clv" model={clv} />
      </div>
    </div>
  );
}

function ModelCard({ title, kind, model }: { title: string; kind: "churn" | "clv"; model: ModelMetrics | null }) {
  if (!model) {
    return (
      <Panel title={title}>
        <p className="text-sm text-ink-soft">
          No trained run is recorded yet. Run scripts/build_backend_data.py to train and score.
        </p>
      </Panel>
    );
  }

  const known = Object.entries(model.metrics).filter(([key]) => METRIC_LABELS[key]);
  const headline = HEADLINE[kind].filter((key) => key in model.metrics);
  const rest = known.filter(([key]) => !headline.includes(key));

  return (
    <Panel title={title} description={`${model.model_version} · trained ${formatDateTime(model.trained_at)}`}>
      <div className="grid grid-cols-3 gap-3">
        {headline.map((key) => {
          const value = model.metrics[key];
          return (
            <div key={key} className="rounded-lg bg-paper px-4 py-3">
              <div className="text-xs text-ink-soft">{METRIC_LABELS[key]}</div>
              <div className="tabular mt-0.5 text-2xl font-semibold tracking-tight">{value.toFixed(value < 5 ? 3 : 1)}</div>
            </div>
          );
        })}
      </div>
      <dl className="mt-4 divide-y divide-line">
        {rest.map(([key, value]) => (
          <div key={key} className="flex items-center justify-between py-2.5 text-sm">
            <dt className="text-ink-soft">{METRIC_LABELS[key]}</dt>
            <dd className="tabular font-medium">{value.toFixed(value < 5 ? 3 : 1)}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
