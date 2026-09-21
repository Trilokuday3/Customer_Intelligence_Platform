import { getChurnByDimension, getDashboardSummary } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import StatTile from "@/components/StatTile";
import SegmentBarChart from "@/components/charts/SegmentBarChart";
import ChurnByDimensionChart from "@/components/charts/ChurnByDimensionChart";

export default async function DashboardPage() {
  const [summary, churnByChannel] = await Promise.all([
    getDashboardSummary(),
    getChurnByDimension("acquisition_channel"),
  ]);

  const segmentData = Object.entries(summary.segment_distribution).map(([segment, count]) => ({ segment, count }));

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-medium">Executive Overview</h1>
        <p className="mt-1 text-sm text-ink-soft">
          As of {formatDate(summary.prediction_date)} · {formatNumber(summary.total_customers)} customers,{" "}
          {formatNumber(summary.scored_customers)} scored
        </p>
      </div>

      <div className="grid grid-cols-2 gap-x-8 gap-y-6 md:grid-cols-5">
        <StatTile label="Total customers" value={formatNumber(summary.total_customers)} />
        <StatTile label="High-risk customers" value={formatNumber(summary.high_risk_count)} tone="risk" />
        <StatTile label="Revenue at risk" value={formatCurrency(summary.revenue_at_risk)} tone="risk" />
        <StatTile label="Mean predicted CLV" value={formatCurrency(summary.mean_predicted_clv)} tone="value" />
        <StatTile label="Mean churn probability" value={formatPercent(summary.mean_churn_probability)} />
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <section className="rounded border border-line bg-surface p-5">
          <h2 className="text-sm font-medium text-ink-soft">Segment distribution</h2>
          <SegmentBarChart data={segmentData} />
        </section>
        <section className="rounded border border-line bg-surface p-5">
          <h2 className="text-sm font-medium text-ink-soft">Churn rate by acquisition channel</h2>
          <ChurnByDimensionChart data={churnByChannel} />
        </section>
      </div>
    </div>
  );
}
