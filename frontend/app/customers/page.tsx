import Link from "next/link";
import { listCustomers } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-medium">Customers</h1>
        <p className="mt-1 text-sm text-ink-soft">{result.total.toLocaleString()} total</p>
      </div>

      <form className="flex flex-wrap items-end gap-4 border-b border-line pb-6" action="/customers">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Search customer ID</span>
          <input
            type="text"
            name="search"
            defaultValue={search}
            placeholder="C000123"
            className="rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Segment</span>
          <select
            name="segment"
            defaultValue={segment ?? ""}
            className="rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          >
            <option value="">All</option>
            <option value="Champions">Champions</option>
            <option value="Steady Regulars">Steady Regulars</option>
            <option value="New / Developing">New / Developing</option>
            <option value="Dormant / Lost">Dormant / Lost</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Plan</span>
          <select
            name="plan"
            defaultValue={plan ?? ""}
            className="rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          >
            <option value="">All</option>
            <option value="bronze">Bronze</option>
            <option value="silver">Silver</option>
            <option value="gold">Gold</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Sort by</span>
          <select
            name="sort_by"
            defaultValue={sortBy}
            className="rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          >
            <option value="churn_probability">Churn risk</option>
            <option value="predicted_clv">Predicted CLV</option>
          </select>
        </label>
        <button type="submit" className="rounded bg-accent px-4 py-1.5 text-sm text-white">
          Apply
        </button>
      </form>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-ink-soft">
            <th className="py-2 font-medium">Customer</th>
            <th className="py-2 font-medium">Plan</th>
            <th className="py-2 font-medium">Channel</th>
            <th className="py-2 font-medium">Segment</th>
            <th className="py-2 font-medium">Churn risk</th>
            <th className="py-2 text-right font-medium">Predicted CLV</th>
          </tr>
        </thead>
        <tbody>
          {result.items.map((item) => (
            <tr key={item.customer_id} className="border-b border-line/60 hover:bg-surface">
              <td className="py-2">
                <Link href={`/customers/${item.customer_id}`} className="text-accent hover:underline">
                  {item.customer_id}
                </Link>
              </td>
              <td className="py-2 capitalize">{item.plan}</td>
              <td className="py-2 capitalize">{item.acquisition_channel.replace("_", " ")}</td>
              <td className="py-2">{item.segment ?? "—"}</td>
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

      <div className="flex items-center justify-between text-sm text-ink-soft">
        <span>
          Page {page} of {totalPages}
        </span>
        <div className="flex gap-3">
          {page > 1 ? (
            <Link className="text-accent hover:underline" href={buildPageHref(params, page - 1)}>
              Previous
            </Link>
          ) : null}
          {page < totalPages ? (
            <Link className="text-accent hover:underline" href={buildPageHref(params, page + 1)}>
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
