import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, getCustomer, getCustomerHistory, getExplanation } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { RISK_BANDS, riskBand } from "@/lib/risk";
import { SEGMENT_COLOR } from "@/lib/segments";
import AnimatedRiskNumber from "@/components/AnimatedRiskNumber";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import type { DriverContribution, HistoryEvent } from "@/lib/types";

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

  const band = customer.churn_probability !== null ? riskBand(customer.churn_probability) : null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={
          <Link href="/customers" className="text-accent hover:underline">
            ← All customers
          </Link>
        }
        title={customer.customer_id}
        description={
          <>
            <span className="capitalize">{customer.plan}</span> plan · {customer.country} · via{" "}
            {customer.acquisition_channel.replaceAll("_", " ")} · signed up {formatDate(customer.signup_date)}
          </>
        }
        meta={
          customer.segment ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-sm font-medium">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: SEGMENT_COLOR[customer.segment] ?? "#667085" }}
                aria-hidden
              />
              {customer.segment}
            </span>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Panel className="lg:col-span-3">
          <div className="text-[13px] text-ink-soft">Churn probability</div>
          {customer.churn_probability !== null && band ? (
            <>
              <div className="mt-1 flex items-baseline gap-3">
                <AnimatedRiskNumber probability={customer.churn_probability} />
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                  style={{ backgroundColor: band.soft, color: band.color }}
                >
                  {band.label} risk
                </span>
              </div>
              <RiskMeter probability={customer.churn_probability} />
            </>
          ) : (
            <div className="mt-2 text-2xl font-semibold text-ink-soft">Not scored</div>
          )}
        </Panel>

        <Panel className="lg:col-span-2">
          <div className="text-[13px] text-ink-soft">Predicted CLV (next 180 days)</div>
          <div className="tabular mt-1 text-4xl font-semibold tracking-tight text-value">
            {customer.predicted_clv !== null ? formatCurrency(customer.predicted_clv) : "—"}
          </div>
          <dl className="tabular mt-5 grid grid-cols-3 gap-3 border-t border-line pt-4 text-sm">
            <div>
              <dt className="text-xs text-ink-soft">Recency</dt>
              <dd className="mt-0.5 font-semibold">
                {customer.rfm.recency_days !== null ? `${customer.rfm.recency_days.toFixed(0)}d` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Orders</dt>
              <dd className="mt-0.5 font-semibold">{formatNumber(customer.rfm.frequency)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Spend</dt>
              <dd className="mt-0.5 font-semibold">{formatCurrency(customer.rfm.monetary)}</dd>
            </div>
          </dl>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {explanation ? <RiskDrivers drivers={explanation.top_drivers} /> : null}
        <HistoryTimeline events={history.events} total={history.total_events} />
      </div>
    </div>
  );
}

function RiskMeter({ probability }: { probability: number }) {
  return (
    <div className="mt-5">
      <div className="relative h-2.5 overflow-hidden rounded-full">
        <div className="absolute inset-0 flex">
          {RISK_BANDS.map((band) => (
            <div key={band.key} className="h-full flex-1" style={{ backgroundColor: band.color, opacity: 0.85 }} />
          ))}
        </div>
      </div>
      <div className="relative h-3">
        <div
          className="absolute top-0 h-3 w-3 -translate-x-1/2 rotate-45 border-l border-t border-ink bg-surface"
          style={{ left: `${Math.min(Math.max(probability, 0.01), 0.99) * 100}%` }}
          aria-hidden
        />
      </div>
      <div className="tabular mt-1 flex justify-between text-xs text-ink-soft">
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>
    </div>
  );
}

function RiskDrivers({ drivers }: { drivers: DriverContribution[] }) {
  const readable = (feature: string) => feature.replace(/^numeric__|^categorical__/, "").replaceAll("_", " ");
  const max = Math.max(...drivers.map((d) => Math.abs(d.shap_value)), 0.0001);
  return (
    <Panel title="Why this score" description="The features pushing this customer's risk up or down.">
      <ul className="flex flex-col gap-3">
        {drivers.map((driver) => {
          const up = driver.shap_value > 0;
          const width = (Math.abs(driver.shap_value) / max) * 50;
          return (
            <li key={driver.feature} className="grid grid-cols-[minmax(7rem,9rem)_1fr_3rem] items-center gap-3 text-sm">
              <span className="truncate capitalize" title={readable(driver.feature)}>
                {readable(driver.feature)}
              </span>
              <span className="relative h-2.5 rounded-full bg-paper" aria-hidden>
                <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
                <span
                  className="absolute inset-y-0 rounded-full"
                  style={{
                    width: `${width}%`,
                    [up ? "left" : "right"]: "50%",
                    backgroundColor: up ? "#e5603f" : "#2f8f6b",
                  }}
                />
              </span>
              <span className={`tabular text-right font-medium ${up ? "text-high" : "text-healthy"}`}>
                {up ? "+" : "−"}
                {Math.abs(driver.shap_value).toFixed(2)}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 text-xs leading-relaxed text-ink-soft">
        Right (orange) raises churn risk, left (green) lowers it. Values are SHAP contributions; see
        docs/explainability_report.md for how direction is computed and its limits.
      </p>
    </Panel>
  );
}

const EVENT_DOT: Record<HistoryEvent["event_source"], string> = {
  order: "#2b5fd9",
  support: "#e5603f",
  interaction: "#98a2b3",
};

function HistoryTimeline({ events, total }: { events: HistoryEvent[]; total: number }) {
  const shown = events.slice(0, 40);
  const days: { day: string; items: HistoryEvent[] }[] = [];
  for (const event of shown) {
    const day = formatDate(event.event_time);
    const last = days[days.length - 1];
    if (last && last.day === day) last.items.push(event);
    else days.push({ day, items: [event] });
  }

  return (
    <Panel
      title="Activity"
      description={`Latest ${shown.length} of ${formatNumber(total)} events, newest first. Blue is an order, orange a support ticket, grey a visit.`}
    >
      <div className="flex max-h-[26rem] flex-col gap-5 overflow-y-auto pr-1">
        {days.map((group) => (
          <div key={group.day}>
            <div className="mb-2 text-xs font-semibold text-ink-soft">{group.day}</div>
            <ul className="ml-1.5 flex flex-col gap-2.5 border-l border-line pl-4">
              {group.items.map((event, index) => (
                <li key={index} className="relative flex items-center justify-between gap-3 text-sm">
                  <span
                    className="absolute -left-[22px] h-2.5 w-2.5 rounded-full ring-4 ring-surface"
                    style={{ backgroundColor: EVENT_DOT[event.event_source] }}
                    aria-hidden
                  />
                  <span>{event.description}</span>
                  {event.amount !== null ? (
                    <span className="tabular shrink-0 font-medium">{formatCurrency(event.amount)}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  );
}
