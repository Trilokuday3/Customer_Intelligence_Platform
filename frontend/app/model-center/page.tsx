import { ApiError, getModelMetrics } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
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
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-medium">Model Center</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Metrics computed once by scripts/build_backend_data.py and read from the model_runs table — never
          recomputed per request. See docs/model_card.md and docs/clv_methodology.md for the full write-up.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <ModelCard title="Churn model" model={churn} />
        <ModelCard title="CLV model" model={clv} />
      </div>
    </div>
  );
}

function ModelCard({ title, model }: { title: string; model: ModelMetrics | null }) {
  return (
    <section className="rounded border border-line bg-surface p-5">
      <h2 className="text-sm font-medium text-ink-soft">{title}</h2>
      {model ? (
        <>
          <p className="tabular mt-1 text-xs text-ink-soft">
            {model.model_version} · trained {formatDateTime(model.trained_at)}
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3">
            {Object.entries(model.metrics)
              .filter(([key]) => METRIC_LABELS[key])
              .map(([key, value]) => (
                <div key={key} className="border-b border-line/60 pb-1">
                  <dt className="text-xs text-ink-soft">{METRIC_LABELS[key]}</dt>
                  <dd className="tabular text-lg">{value.toFixed(value < 5 ? 3 : 1)}</dd>
                </div>
              ))}
          </dl>
        </>
      ) : (
        <p className="mt-3 text-sm text-ink-soft">No trained run recorded yet — run scripts/build_backend_data.py.</p>
      )}
    </section>
  );
}
