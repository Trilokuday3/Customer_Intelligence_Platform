import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, getSegment } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import RiskBadge from "@/components/RiskBadge";

export default async function SegmentDetailPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const detail = await getSegment(decodeURIComponent(name)).catch((error) => {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/segments" className="text-sm text-accent hover:underline">
          ← All segments
        </Link>
        <h1 className="mt-2 text-2xl font-medium">{detail.summary.segment}</h1>
        <p className="mt-1 text-sm text-ink-soft">
          {formatNumber(detail.summary.size)} customers · mean churn {formatPercent(detail.summary.mean_churn_probability)}{" "}
          · mean CLV {formatCurrency(detail.summary.mean_predicted_clv)}
        </p>
      </div>

      <section>
        <h2 className="text-sm font-medium text-ink-soft">Top at-risk in this segment</h2>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-ink-soft">
              <th className="py-2 font-medium">Customer</th>
              <th className="py-2 font-medium">Plan</th>
              <th className="py-2 font-medium">Churn risk</th>
              <th className="py-2 text-right font-medium">Predicted CLV</th>
            </tr>
          </thead>
          <tbody>
            {detail.top_at_risk.map((item) => (
              <tr key={item.customer_id} className="border-b border-line/60 hover:bg-surface">
                <td className="py-2">
                  <Link href={`/customers/${item.customer_id}`} className="text-accent hover:underline">
                    {item.customer_id}
                  </Link>
                </td>
                <td className="py-2 capitalize">{item.plan}</td>
                <td className="py-2">
                  <RiskBadge probability={item.churn_probability} />
                </td>
                <td className="tabular py-2 text-right">
                  {item.predicted_clv !== null ? formatCurrency(item.predicted_clv) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
