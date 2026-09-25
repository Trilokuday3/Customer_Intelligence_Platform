import { getChurnByDimension, getDashboardSummary, getRiskDistribution } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import KpiStrip from "@/components/KpiStrip";
import Panel from "@/components/Panel";
import PageHeader, { AsOfChip } from "@/components/PageHeader";
import RiskRibbon from "@/components/RiskRibbon";
import SegmentBarChart from "@/components/charts/SegmentBarChart";
import ChurnByDimensionChart from "@/components/charts/ChurnByDimensionChart";

export default async function DashboardPage() {
  const [summary, churnByChannel, distribution] = await Promise.all([
    getDashboardSummary(),
    getChurnByDimension("acquisition_channel"),
    // The ribbon is an enhancement: an older API without this route must not break the page.
    getRiskDistribution().catch(() => null),
  ]);

  const segmentData = Object.entries(summary.segment_distribution).map(([segment, count]) => ({ segment, count }));
  const highRiskShare = summary.scored_customers ? summary.high_risk_count / summary.scored_customers : 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Overview"
        description="Who is likely to leave, what that puts at risk, and where the customer base sits today."
        meta={<AsOfChip label={`Scored as of ${formatDate(summary.prediction_date)}`} />}
      />

      <KpiStrip
        items={[
          {
            label: "Revenue at risk",
            value: formatCurrency(summary.revenue_at_risk),
            tone: "critical",
            note: "Predicted CLV of high-risk customers",
          },
          {
            label: "High-risk customers",
            value: formatNumber(summary.high_risk_count),
            tone: "critical",
            note: `${formatPercent(highRiskShare, 0)} of scored`,
          },
          {
            label: "Customers",
            value: formatNumber(summary.total_customers),
            note: `${formatNumber(summary.scored_customers)} scored`,
          },
          { label: "Mean predicted CLV", value: formatCurrency(summary.mean_predicted_clv), tone: "value", note: "Next 180 days" },
          { label: "Mean churn probability", value: formatPercent(summary.mean_churn_probability), note: "Across scored customers" },
        ]}
      />

      {distribution && distribution.total > 0 ? (
        <Panel
          title="Churn risk across every scored customer"
          description="Each bar is a 5-point slice of churn probability. Colour is the risk band."
        >
          <RiskRibbon bins={distribution.bins} total={distribution.total} />
        </Panel>
      ) : null}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Customers by segment" description="Behavioural clusters, named from how each group buys.">
          <div className="overflow-x-auto">
            <SegmentBarChart data={segmentData} />
          </div>
        </Panel>
        <Panel title="Churn rate by acquisition channel" description="Mean predicted churn probability per channel.">
          <div className="overflow-x-auto">
            <ChurnByDimensionChart data={churnByChannel} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
