import { getDrift, getHealth } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import type { DriftMetric, DriftReportResponse } from "@/lib/types";

const SEVERITY: Record<DriftMetric["severity"], { label: string; color: string; soft: string }> = {
  stable: { label: "Stable", color: "#2f8f6b", soft: "#e2f3ec" },
  moderate: { label: "Moderate", color: "#c9931a", soft: "#fbf0d4" },
  significant: { label: "Significant", color: "#b42318", soft: "#fbe3e0" },
};

function SeverityPill({ severity }: { severity: DriftMetric["severity"] }) {
  const tone = SEVERITY[severity];
  return (
    <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ backgroundColor: tone.soft, color: tone.color }}>
      {tone.label}
    </span>
  );
}

export default async function MonitoringPage() {
  const [health, churnDrift, clvDrift] = await Promise.all([getHealth(), getDrift("churn"), getDrift("clv")]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Monitoring"
        description="Is the data fresh, and does the population the models see today still look like the one they were trained on?"
        meta={
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: health.database_connected ? "#2f8f6b" : "#b42318" }}
              aria-hidden
            />
            {health.database_connected ? "Database connected" : "Database unreachable"}
          </span>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel title="Data freshness" className="xl:col-span-1">
          <dl className="flex flex-col gap-4">
            <div>
              <dt className="text-xs text-ink-soft">Latest order</dt>
              <dd className="tabular mt-0.5 text-lg font-semibold">
                {health.latest_order_date ? formatDateTime(health.latest_order_date) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Latest scoring run</dt>
              <dd className="tabular mt-0.5 text-lg font-semibold">
                {health.latest_prediction_date ? formatDateTime(health.latest_prediction_date) : "—"}
              </dd>
            </div>
          </dl>
        </Panel>

        <Panel title="Table sizes" className="xl:col-span-2">
          <dl className="tabular grid grid-cols-2 gap-4 sm:grid-cols-5">
            {Object.entries(health.table_row_counts).map(([table, count]) => (
              <div key={table}>
                <dt className="text-xs capitalize text-ink-soft">{table}</dt>
                <dd className="mt-0.5 text-lg font-semibold">{formatNumber(count)}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>

      <DriftSection title="Churn model drift" report={churnDrift} />
      <DriftSection title="CLV model drift" report={clvDrift} />
    </div>
  );
}

function DriftSection({ title, report }: { title: string; report: DriftReportResponse }) {
  return (
    <Panel
      title={title}
      description={`Population Stability Index against the training population. Report date ${report.report_date}.`}
      flush
    >
      {report.feature_drift.length === 0 ? (
        <p className="px-5 pb-5 text-sm text-ink-soft">
          No drift report yet. Run scripts/build_backend_data.py to compare the training population with the latest
          snapshot.
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Feature</th>
              <th className="num hidden md:table-cell">Reference mean</th>
              <th className="num hidden md:table-cell">Current mean</th>
              <th className="num">PSI</th>
              <th className="num">Status</th>
            </tr>
          </thead>
          <tbody>
            {report.feature_drift.map((row) => (
              <tr key={row.metric_name}>
                <td className="font-medium">{row.metric_name}</td>
                <td className="tabular num hidden md:table-cell">{row.reference_mean.toFixed(2)}</td>
                <td className="tabular num hidden md:table-cell">{row.current_mean.toFixed(2)}</td>
                <td className="tabular num">{row.psi.toFixed(3)}</td>
                <td className="num">
                  <SeverityPill severity={row.severity} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="border-t border-line px-5 py-4">
        {report.has_prediction_baseline ? (
          report.prediction_drift.map((row) => (
            <div key={row.metric_name} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span className="text-ink-soft">Prediction drift ({row.metric_name})</span>
              <span className="tabular font-medium">
                {row.reference_mean.toFixed(3)} → {row.current_mean.toFixed(3)}
              </span>
              <span className="tabular text-ink-soft">PSI {row.psi.toFixed(3)}</span>
              <SeverityPill severity={row.severity} />
            </div>
          ))
        ) : (
          <p className="text-sm text-ink-soft">
            No earlier scoring run to compare with. Prediction drift appears after the batch job has run twice.
          </p>
        )}
      </div>
    </Panel>
  );
}
