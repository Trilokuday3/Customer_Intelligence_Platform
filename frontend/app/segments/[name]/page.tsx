import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, getSegment } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import KpiStrip from "@/components/KpiStrip";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import RiskBadge from "@/components/RiskBadge";

export default async function SegmentDetailPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const detail = await getSegment(decodeURIComponent(name)).catch((error) => {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={
          <Link href="/segments" className="text-accent hover:underline">
            ← All segments
          </Link>
        }
        title={detail.summary.segment}
      />

      <div className="max-w-2xl">
        <KpiStrip
          items={[
            { label: "Customers", value: formatNumber(detail.summary.size) },
            { label: "Mean churn probability", value: formatPercent(detail.summary.mean_churn_probability), tone: "critical" },
            { label: "Mean predicted CLV", value: formatCurrency(detail.summary.mean_predicted_clv), tone: "value" },
          ]}
        />
      </div>

      <Panel title="Most at risk in this segment" description="Highest churn probability first." flush>
        <table className="data-table">
          <thead>
            <tr>
              <th>Customer</th>
              <th>Plan</th>
              <th>Churn risk</th>
              <th className="num">Predicted CLV</th>
            </tr>
          </thead>
          <tbody>
            {detail.top_at_risk.map((item) => (
              <tr key={item.customer_id}>
                <td>
                  <Link href={`/customers/${item.customer_id}`} className="font-medium text-accent hover:underline">
                    {item.customer_id}
                  </Link>
                </td>
                <td className="capitalize">{item.plan}</td>
                <td>
                  <RiskBadge probability={item.churn_probability} />
                </td>
                <td className="tabular num">{item.predicted_clv !== null ? formatCurrency(item.predicted_clv) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
