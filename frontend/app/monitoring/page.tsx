import { getDrift, getHealth } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { DriftMetric, DriftReportResponse } from "@/lib/types";

const SEVERITY_TONE: Record<DriftMetric["severity"], string> = {
  stable: "text-retain",
  moderate: "text-value",
  significant: "text-risk",
};

export default async function MonitoringPage() {
  const [health, churnDrift, clvDrift] = await Promise.all([
    getHealth(),
    getDrift("churn"),
    getDrift("clv"),
  ]);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-medium">Monitoring</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Data freshness and drift — whether the population a model now sees still looks like the one it was
          trained or last scored on.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <span
          className={`h-2.5 w-2.5 rounded-full ${health.database_connected ? "bg-retain" : "bg-risk"}`}
          aria-hidden
        />
        <span className="text-sm">{health.database_connected ? "Database connected" : "Database unreachable"}</span>
      </div>

      <section className="rounded border border-line bg-surface p-5">
        <h2 className="text-sm font-medium text-ink-soft">Table row counts</h2>
        <dl className="tabular mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
          {Object.entries(health.table_row_counts).map(([table, count]) => (
            <div key={table}>
              <dt className="text-xs text-ink-soft capitalize">{table}</dt>
              <dd className="text-lg">{formatNumber(count)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rounded border border-line bg-surface p-5">
        <h2 className="text-sm font-medium text-ink-soft">Freshness</h2>
        <dl className="mt-3 flex gap-10">
          <div>
            <dt className="text-xs text-ink-soft">Latest order</dt>
            <dd className="tabular text-lg">{health.latest_order_date ? formatDateTime(health.latest_order_date) : "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-soft">Latest prediction run</dt>
            <dd className="tabular text-lg">
              {health.latest_prediction_date ? formatDateTime(health.latest_prediction_date) : "—"}
            </dd>
          </div>
        </dl>
      </section>

      <DriftSection title="Churn model drift" report={churnDrift} />
      <DriftSection title="CLV model drift" report={clvDrift} />
    </div>
  );
}

function DriftSection({ title, report }: { title: string; report: DriftReportResponse }) {
  return (
    <section className="rounded border border-line bg-surface p-5">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-medium text-ink-soft">{title}</h2>
        <span className="tabular text-xs text-ink-soft">as of {report.report_date}</span>
      </div>

      {report.feature_drift.length === 0 ? (
        <p className="mt-3 text-sm text-ink-soft">
          No drift report yet — run scripts/build_backend_data.py to compare the training population against the
          latest snapshot.
        </p>
      ) : (
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-ink-soft">
              <th className="py-2 font-medium">Feature</th>
              <th className="py-2 text-right font-medium">Reference mean</th>
              <th className="py-2 text-right font-medium">Current mean</th>
              <th className="py-2 text-right font-medium">PSI</th>
              <th className="py-2 text-right font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {report.feature_drift.map((row) => (
              <tr key={row.metric_name} className="border-b border-line/60">
                <td className="py-2">{row.metric_name}</td>
                <td className="tabular py-2 text-right">{row.reference_mean.toFixed(2)}</td>
                <td className="tabular py-2 text-right">{row.current_mean.toFixed(2)}</td>
                <td className="tabular py-2 text-right">{row.psi.toFixed(3)}</td>
                <td className={`py-2 text-right ${SEVERITY_TONE[row.severity]}`}>{row.severity}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="mt-4 border-t border-line pt-4">
        {report.has_prediction_baseline ? (
          report.prediction_drift.map((row) => (
            <div key={row.metric_name} className="flex items-center gap-4 text-sm">
              <span className="text-ink-soft">Prediction drift ({row.metric_name})</span>
              <span className="tabular">{row.reference_mean.toFixed(3)} → {row.current_mean.toFixed(3)}</span>
              <span className={`tabular ${SEVERITY_TONE[row.severity]}`}>PSI {row.psi.toFixed(3)} · {row.severity}</span>
            </div>
          ))
        ) : (
          <p className="text-sm text-ink-soft">
            No prior scoring run to compare against — prediction drift needs two runs of
            scripts/build_backend_data.py and will appear after the next one.
          </p>
        )}
      </div>
    </section>
  );
}
