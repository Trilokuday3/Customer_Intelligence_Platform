import { getCohorts } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";

// Retention is good news, so it uses the action blue rather than the risk scale.
function cellStyle(value: number) {
  // Most cells sit in a narrow band, so stretch 30%..70% across the whole ramp.
  const strength = Math.min(Math.max((value - 30) / 40, 0), 1);
  return {
    backgroundColor: `rgba(43, 95, 217, ${(0.06 + strength * 0.94).toFixed(2)})`,
    color: strength > 0.45 ? "#ffffff" : "#101828",
  };
}

export default async function CohortsPage() {
  const rows = await getCohorts();

  const months = [...new Set(rows.map((r) => r.cohort_month))].sort();
  const ages = [...new Set(rows.map((r) => r.cohort_age_months))].sort((a, b) => a - b);
  const byKey = new Map(rows.map((r) => [`${r.cohort_month}:${r.cohort_age_months}`, r.retained_pct]));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Cohort retention"
        description="Of the customers who signed up in a given month, the share who still placed a qualifying order N months later. Read across a row to see how fast a cohort fades."
      />

      <Panel title="Retention by signup month" description="Columns are months since signup. Darker means more of the cohort is still buying.">
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-[3px] text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 bg-surface pr-3 text-left text-[13px] font-medium text-ink-soft">Cohort</th>
                {ages.map((age) => (
                  <th key={age} className="tabular px-1 pb-1 text-center text-xs font-medium text-ink-soft">
                    {age}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {months.map((month) => (
                <tr key={month}>
                  <td className="tabular sticky left-0 bg-surface pr-3 text-[13px] text-ink-soft">{month}</td>
                  {ages.map((age) => {
                    const value = byKey.get(`${month}:${age}`);
                    return (
                      <td key={age} className="p-0">
                        {value !== undefined ? (
                          <div
                            className="tabular flex h-9 w-12 items-center justify-center rounded-md text-xs font-medium"
                            style={cellStyle(value)}
                            title={`${month}, month ${age}: ${value.toFixed(1)}% retained`}
                          >
                            {value.toFixed(0)}
                          </div>
                        ) : (
                          <div className="h-9 w-12" />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-5 flex items-center gap-3 text-xs text-ink-soft">
          <span>30% or less</span>
          <span
            className="h-2 w-40 rounded-full"
            style={{ background: "linear-gradient(to right, rgba(43,95,217,0.08), rgba(43,95,217,1))" }}
            aria-hidden
          />
          <span>70% or more retained</span>
        </div>
      </Panel>
    </div>
  );
}
