"use client";

import { useMemo, useState } from "react";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import KpiStrip from "@/components/KpiStrip";
import Panel from "@/components/Panel";
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
    return <p className="text-sm text-ink-soft">No segments available. Run scripts/build_backend_data.py first.</p>;
  }

  const positive = scenario.netValue >= 0;

  return (
    <div className="flex flex-col gap-6">
      <Panel title="Scenario" description="Change any input and every number below updates.">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Segment
            <select value={segmentName} onChange={(e) => setSegmentName(e.target.value)} className="field w-48">
              {segments.map((s) => (
                <option key={s.segment} value={s.segment}>
                  {s.segment}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Cost per customer (₹)
            <input
              type="number"
              value={interventionCost}
              onChange={(e) => setInterventionCost(Number(e.target.value))}
              className="field tabular w-36"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            At-risk customers targeted (%)
            <input
              type="number"
              value={targetPct}
              min={0}
              max={100}
              onChange={(e) => setTargetPct(Number(e.target.value))}
              className="field tabular w-40"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-soft">
            Assumed save rate (%)
            <input
              type="number"
              value={upliftPct}
              min={0}
              max={100}
              onChange={(e) => setUpliftPct(Number(e.target.value))}
              className="field tabular w-36"
            />
          </label>
        </div>
      </Panel>

      <div
        className="rounded-[10px] border px-5 py-4 text-sm leading-relaxed"
        style={{ borderColor: "#e8d49a", backgroundColor: "#fbf3da" }}
        role="note"
      >
        <strong className="font-semibold">This is an assumption, not a measurement.</strong> The {upliftPct}% save rate is
        a scenario input you set; no experiment produced it. Treat every figure as &ldquo;if this uplift held&rdquo;, not
        as a forecast. Only a randomised test can establish a real save rate.
      </div>

      <KpiStrip
        items={[
          { label: "At risk in segment", value: formatNumber(Math.round(scenario.atRisk)) },
          { label: "Targeted", value: formatNumber(Math.round(scenario.targeted)) },
          { label: "Assumed retained value", value: formatCurrency(scenario.retainedValue), tone: "value" },
          { label: "Campaign cost", value: formatCurrency(scenario.campaignCost), tone: "critical" },
          {
            label: `Net value at ${upliftPct}% save rate`,
            value: formatCurrency(scenario.netValue),
            tone: positive ? "healthy" : "critical",
            note: positive ? "Campaign pays for itself" : "Campaign costs more than it saves",
          },
        ]}
      />

      <Panel title="Sensitivity to the save rate" description="The same campaign under different assumed uplifts." flush>
        <table className="data-table">
          <thead>
            <tr>
              <th>Assumed save rate</th>
              <th className="num">Retained value</th>
              <th className="num hidden sm:table-cell">Campaign cost</th>
              <th className="num">Net value</th>
            </tr>
          </thead>
          <tbody>
            {UPLIFT_SCENARIOS.map((pct) => {
              const targeted = scenario.atRisk * (targetPct / 100);
              const retained = targeted * (pct / 100);
              const retainedValue = retained * segment.mean_predicted_clv;
              const campaignCost = targeted * interventionCost;
              const netValue = retainedValue - campaignCost;
              const selected = pct === upliftPct;
              return (
                <tr key={pct} style={selected ? { backgroundColor: "#eef3fd" } : undefined}>
                  <td className="tabular font-medium">
                    {formatPercent(pct / 100, 0)}
                    {selected ? <span className="ml-2 text-xs font-normal text-accent">selected</span> : null}
                  </td>
                  <td className="tabular num">{formatCurrency(retainedValue)}</td>
                  <td className="tabular num hidden sm:table-cell">{formatCurrency(campaignCost)}</td>
                  <td className={`tabular num font-medium ${netValue >= 0 ? "text-healthy" : "text-critical"}`}>
                    {formatCurrency(netValue)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
