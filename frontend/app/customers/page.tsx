import Link from "next/link";
import { listCustomers } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { SEGMENT_COLOR } from "@/lib/segments";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import RiskBadge from "@/components/RiskBadge";

const PAGE_SIZE = 25;

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const search = typeof params.search === "string" ? params.search : undefined;
  const segment = typeof params.segment === "string" ? params.segment : undefined;
  const plan = typeof params.plan === "string" ? params.plan : undefined;
  const sortBy = params.sort_by === "predicted_clv" ? "predicted_clv" : "churn_probability";
  const page = Number(params.page ?? "1") || 1;

  const result = await listCustomers({
    search,
    segment,
    plan,
    sort_by: sortBy,
    page,
    page_size: PAGE_SIZE,
  });

  const totalPages = Math.max(Math.ceil(result.total / PAGE_SIZE), 1);
  const firstRow = result.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRow = Math.min(page * PAGE_SIZE, result.total);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Customers"
        description={`${result.total.toLocaleString("en-IN")} customers. Sorted by ${
          sortBy === "predicted_clv" ? "predicted lifetime value" : "churn risk"
        }, highest first.`}
      />

      <Panel>
        <form className="flex flex-wrap items-end gap-4" action="/customers">
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Customer ID
            <input type="text" name="search" defaultValue={search} placeholder="C000123" className="field w-44" />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Segment
            <select name="segment" defaultValue={segment ?? ""} className="field w-44">
              <option value="">All segments</option>
              <option value="Champions">Champions</option>
              <option value="Steady Regulars">Steady Regulars</option>
              <option value="New / Developing">New / Developing</option>
              <option value="Dormant / Lost">Dormant / Lost</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Plan
            <select name="plan" defaultValue={plan ?? ""} className="field w-36">
              <option value="">All plans</option>
              <option value="bronze">Bronze</option>
              <option value="silver">Silver</option>
              <option value="gold">Gold</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Sort by
            <select name="sort_by" defaultValue={sortBy} className="field w-40">
              <option value="churn_probability">Churn risk</option>
              <option value="predicted_clv">Predicted CLV</option>
            </select>
          </label>
          <button type="submit" className="btn-primary">
            Apply filters
          </button>
          {search || segment || plan ? (
            <Link href="/customers" className="pb-2 text-sm text-accent hover:underline">
              Clear
            </Link>
          ) : null}
        </form>
      </Panel>

      <Panel flush>
        <table className="data-table">
          <thead>
            <tr>
              <th>Customer</th>
              <th>Plan</th>
              <th>Channel</th>
              <th>Segment</th>
              <th>Churn risk</th>
              <th className="num">Predicted CLV</th>
            </tr>
          </thead>
          <tbody>
            {result.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-10 text-center text-ink-soft">
                  No customers match these filters. Clear a filter or check the customer ID.
                </td>
              </tr>
            ) : null}
            {result.items.map((item) => (
              <tr key={item.customer_id}>
                <td>
                  <Link href={`/customers/${item.customer_id}`} className="font-medium text-accent hover:underline">
                    {item.customer_id}
                  </Link>
                </td>
                <td className="capitalize">{item.plan}</td>
                <td className="capitalize">{item.acquisition_channel.replaceAll("_", " ")}</td>
                <td>
                  {item.segment ? (
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: SEGMENT_COLOR[item.segment] ?? "#667085" }}
                        aria-hidden
                      />
                      {item.segment}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  <RiskBadge probability={item.churn_probability} />
                </td>
                <td className="tabular num">{item.predicted_clv !== null ? formatCurrency(item.predicted_clv) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="flex items-center justify-between text-sm text-ink-soft">
        <span className="tabular">
          {firstRow}–{lastRow} of {result.total.toLocaleString("en-IN")} · page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          {page > 1 ? (
            <Link
              className="rounded-lg border border-line-strong bg-surface px-3 py-1.5 font-medium text-ink hover:bg-paper"
              href={buildPageHref(params, page - 1)}
            >
              Previous
            </Link>
          ) : null}
          {page < totalPages ? (
            <Link
              className="rounded-lg border border-line-strong bg-surface px-3 py-1.5 font-medium text-ink hover:bg-paper"
              href={buildPageHref(params, page + 1)}
            >
              Next
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function buildPageHref(params: { [key: string]: string | string[] | undefined }, page: number): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === "page") continue;
    if (typeof value === "string" && value) query.set(key, value);
  }
  query.set("page", String(page));
  return `/customers?${query.toString()}`;
}
