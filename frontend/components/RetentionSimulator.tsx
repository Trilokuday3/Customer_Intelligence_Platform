"use client";

import { useMemo, useState } from "react";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import type { SegmentSummary } from "@/lib/types";

const UPLIFT_SCENARIOS = [5, 10, 15, 20, 25, 30];

export default function RetentionSimulator({ segments }: { segments: SegmentSummary[] }) {
  const [segmentName, setSegmentName] = useState(segments[0]?.segment ?? "");
  const [interventionCost, setInterventionCost] = useState(150);
  const [targetPct, setTargetPct] = useState(100);
  const [upliftPct, setUpliftPct] = useState(15);

  const segment = segments.find((s) => s.segment === segmentName) ?? segments[0];

  const scenario = useMemo(() => {
    if (!segment) return null;
    const atRisk = segment.size * segment.mean_churn_probability;
    const targeted = atRisk * (targetPct / 100);
    const retained = targeted * (upliftPct / 100);
    const retainedValue = retained * segment.mean_predicted_clv;
    const campaignCost = targeted * interventionCost;
    const netValue = retainedValue - campaignCost;
    return { atRisk, targeted, retained, retainedValue, campaignCost, netValue };
  }, [segment, targetPct, upliftPct, interventionCost]);

  if (!segment || !scenario) {
    return <p className="text-sm text-ink-soft">No segments available — run scripts/build_backend_data.py first.</p>;
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end gap-6 border-b border-line pb-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Segment</span>
          <select
            value={segmentName}
            onChange={(e) => setSegmentName(e.target.value)}
            className="rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          >
            {segments.map((s) => (
              <option key={s.segment} value={s.segment}>
                {s.segment}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Intervention cost / customer</span>
          <input
            type="number"
            value={interventionCost}
            onChange={(e) => setInterventionCost(Number(e.target.value))}
            className="tabular w-32 rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">% of at-risk customers targeted</span>
          <input
            type="number"
            value={targetPct}
            min={0}
            max={100}
            onChange={(e) => setTargetPct(Number(e.target.value))}
            className="tabular w-24 rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-ink-soft">Assumed save/uplift rate</span>
          <input
            type="number"
            value={upliftPct}
            min={0}
            max={100}
            onChange={(e) => setUpliftPct(Number(e.target.value))}
            className="tabular w-24 rounded border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>
      </div>

      <div className="rounded border border-value bg-value-soft p-4 text-sm text-ink">
        <strong>Assumption, not a measurement.</strong> The {upliftPct}% save rate above is a scenario input you set —
        it is not derived from an experiment. Treat every number below as &ldquo;if this uplift held,&rdquo; not as a
        forecast.
        See guide section 17/18: only a randomized experiment can establish a real causal save rate.
      </div>

      <div className="grid grid-cols-2 gap-x-8 gap-y-6 md:grid-cols-4">
        <Stat label="At-risk in segment" value={formatNumber(Math.round(scenario.atRisk))} />
        <Stat label="Targeted customers" value={formatNumber(Math.round(scenario.targeted))} />
        <Stat label="Assumed retained value" value={formatCurrency(scenario.retainedValue)} tone="value" />
        <Stat label="Campaign cost" value={formatCurrency(scenario.campaignCost)} tone="risk" />
      </div>

      <div>
        <div className={`tabular text-3xl font-medium ${scenario.netValue >= 0 ? "text-retain" : "text-risk"}`}>
          {formatCurrency(scenario.netValue)}
        </div>
        <div className="text-sm text-ink-soft">Assumed net value at {upliftPct}% uplift</div>
      </div>

      <section>
        <h2 className="text-sm font-medium text-ink-soft">Sensitivity across uplift assumptions</h2>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-ink-soft">
              <th className="py-2 font-medium">Assumed uplift</th>
              <th className="py-2 text-right font-medium">Retained value</th>
              <th className="py-2 text-right font-medium">Campaign cost</th>
              <th className="py-2 text-right font-medium">Net value</th>
            </tr>
          </thead>
          <tbody>
            {UPLIFT_SCENARIOS.map((pct) => {
              const targeted = scenario.atRisk * (targetPct / 100);
              const retained = targeted * (pct / 100);
              const retainedValue = retained * segment.mean_predicted_clv;
              const campaignCost = targeted * interventionCost;
              const netValue = retainedValue - campaignCost;
              return (
                <tr key={pct} className={`border-b border-line/60 ${pct === upliftPct ? "bg-value-soft" : ""}`}>
                  <td className="tabular py-2">{formatPercent(pct / 100, 0)}</td>
                  <td className="tabular py-2 text-right">{formatCurrency(retainedValue)}</td>
                  <td className="tabular py-2 text-right">{formatCurrency(campaignCost)}</td>
                  <td className={`tabular py-2 text-right ${netValue >= 0 ? "text-retain" : "text-risk"}`}>
                    {formatCurrency(netValue)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "value" | "risk" }) {
  const toneClass = tone === "value" ? "text-value" : tone === "risk" ? "text-risk" : "text-ink";
  return (
    <div className="border-b-2 border-line pb-3">
      <div className={`tabular text-2xl font-medium ${toneClass}`}>{value}</div>
      <div className="mt-1 text-sm text-ink-soft">{label}</div>
    </div>
  );
}
