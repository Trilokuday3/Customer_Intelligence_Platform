// The single risk scale. Every colour that means "how likely to churn"
// comes from here so pills, bars, meters and charts always agree.
export type RiskBandKey = "healthy" | "watch" | "high" | "critical";

export interface RiskBand {
  key: RiskBandKey;
  label: string;
  color: string;
  soft: string;
}

export const RISK_BANDS: RiskBand[] = [
  { key: "healthy", label: "Healthy", color: "#2f8f6b", soft: "#e2f3ec" },
  { key: "watch", label: "Watch", color: "#c9931a", soft: "#fbf0d4" },
  { key: "high", label: "High", color: "#e5603f", soft: "#fde6df" },
  { key: "critical", label: "Critical", color: "#b42318", soft: "#fbe3e0" },
];

/** Bands are 0.25 wide, so the "high" boundary sits at the 0.5 high-risk cut-off. */
export function riskBand(probability: number): RiskBand {
  if (probability >= 0.75) return RISK_BANDS[3];
  if (probability >= 0.5) return RISK_BANDS[2];
  if (probability >= 0.25) return RISK_BANDS[1];
  return RISK_BANDS[0];
}
