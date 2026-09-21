import { notFound } from "next/navigation";
import { ApiError, getCustomer, getCustomerHistory, getExplanation } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";
import AnimatedRiskNumber from "@/components/AnimatedRiskNumber";
import type { DriverContribution } from "@/lib/types";

export default async function CustomerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const customer = await getCustomer(id).catch((error) => {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });

  const [history, explanation] = await Promise.all([
    getCustomerHistory(id),
    getExplanation(id).catch((error) => {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }),
  ]);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-medium">{customer.customer_id}</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {customer.plan} plan · {customer.country} · via {customer.acquisition_channel.replace("_", " ")} · signed up{" "}
            {new Date(customer.signup_date).toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" })}
          </p>
        </div>
        {customer.segment ? (
          <span className="rounded border border-line px-3 py-1 text-sm text-ink-soft">{customer.segment}</span>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-8 border-b border-line pb-8 md:grid-cols-3">
        <div>
          <div className="text-sm text-ink-soft">Churn probability</div>
          {customer.churn_probability !== null ? (
            <AnimatedRiskNumber probability={customer.churn_probability} />
          ) : (
            <div className="tabular text-3xl text-ink-soft">Not scored</div>
          )}
        </div>
        <div>
          <div className="text-sm text-ink-soft">Predicted CLV (180d)</div>
          <div className="tabular text-3xl font-medium text-value">
            {customer.predicted_clv !== null ? formatCurrency(customer.predicted_clv) : "—"}
          </div>
        </div>
        <div>
          <div className="text-sm text-ink-soft">RFM</div>
          <dl className="tabular mt-1 grid grid-cols-3 gap-2 text-sm">
            <div>
              <dt className="text-ink-soft">Recency</dt>
              <dd>{customer.rfm.recency_days !== null ? `${customer.rfm.recency_days.toFixed(0)}d` : "—"}</dd>
            </div>
            <div>
              <dt className="text-ink-soft">Orders</dt>
              <dd>{formatNumber(customer.rfm.frequency)}</dd>
            </div>
            <div>
              <dt className="text-ink-soft">Spend</dt>
              <dd>{formatCurrency(customer.rfm.monetary)}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {explanation ? <RiskDrivers drivers={explanation.top_drivers} /> : null}
        <HistoryTimeline events={history.events} />
      </div>
    </div>
  );
}

function RiskDrivers({ drivers }: { drivers: DriverContribution[] }) {
  const readable = (feature: string) => feature.replace(/^numeric__|^categorical__/, "").replaceAll("_", " ");
  return (
    <section>
      <h2 className="text-sm font-medium text-ink-soft">Risk drivers</h2>
      <ul className="mt-3 flex flex-col gap-2">
        {drivers.map((driver) => (
          <li key={driver.feature} className="flex items-center justify-between border-b border-line/60 py-1.5 text-sm">
            <span className="capitalize">{readable(driver.feature)}</span>
            <span className={`tabular ${driver.shap_value > 0 ? "text-risk" : "text-retain"}`}>
              {driver.shap_value > 0 ? "↑" : "↓"} {Math.abs(driver.shap_value).toFixed(2)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-ink-soft">
        ↑ pushes toward churn risk, ↓ pushes toward retention — see docs/explainability_report.md for how direction is
        computed and its limits.
      </p>
    </section>
  );
}

function HistoryTimeline({ events }: { events: { event_time: string; event_source: string; description: string; amount: number | null }[] }) {
  return (
    <section>
      <h2 className="text-sm font-medium text-ink-soft">History</h2>
      <ul className="mt-3 flex max-h-96 flex-col gap-2 overflow-y-auto">
        {events.slice(0, 40).map((event, index) => (
          <li key={index} className="flex items-center justify-between border-b border-line/60 py-1.5 text-sm">
            <span>
              <span className="text-ink-soft">{formatDateTime(event.event_time)}</span> — {event.description}
            </span>
            {event.amount !== null ? <span className="tabular">{formatCurrency(event.amount)}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
