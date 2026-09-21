import { getCohorts } from "@/lib/api";

export default async function CohortsPage() {
  const rows = await getCohorts();

  const months = [...new Set(rows.map((r) => r.cohort_month))].sort();
  const ages = [...new Set(rows.map((r) => r.cohort_age_months))].sort((a, b) => a - b);
  const byKey = new Map(rows.map((r) => [`${r.cohort_month}:${r.cohort_age_months}`, r.retained_pct]));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-medium">Cohort Retention</h1>
        <p className="mt-1 text-sm text-ink-soft">
          % of each signup cohort with a qualifying order, by months since signup.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 bg-paper py-1 pr-4 text-left font-medium text-ink-soft">Cohort</th>
              {ages.map((age) => (
                <th key={age} className="tabular px-2 py-1 text-center font-medium text-ink-soft">
                  {age}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {months.map((month) => (
              <tr key={month}>
                <td className="sticky left-0 bg-paper py-1 pr-4 text-ink-soft">{month}</td>
                {ages.map((age) => {
                  const value = byKey.get(`${month}:${age}`);
                  return (
                    <td key={age} className="p-0.5">
                      {value !== undefined ? (
                        <div
                          className="tabular flex h-10 w-14 items-center justify-center rounded-sm text-xs"
                          style={{
                            backgroundColor: `rgba(41, 105, 79, ${Math.min(value / 70, 1).toFixed(2)})`,
                            color: value > 35 ? "#ffffff" : "#14181f",
                          }}
                        >
                          {value.toFixed(0)}
                        </div>
                      ) : (
                        <div className="h-10 w-14" />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
