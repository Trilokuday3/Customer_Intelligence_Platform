import { riskBand } from "@/lib/risk";

/** The headline risk number on Customer 360 eases in on load. Pure CSS (see
 * .risk-reveal in globals.css), so the correct value is in the server-rendered
 * HTML from the start; reduced-motion users get no animation. */
export default function AnimatedRiskNumber({ probability }: { probability: number }) {
  const band = riskBand(probability);
  return (
    <span className="risk-reveal tabular text-5xl font-semibold tracking-tight" style={{ color: band.color }}>
      {(probability * 100).toFixed(1)}%
    </span>
  );
}
