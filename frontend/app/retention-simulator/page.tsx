import { listSegments } from "@/lib/api";
import RetentionSimulator from "@/components/RetentionSimulator";

export default async function RetentionSimulatorPage() {
  const segments = await listSegments();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-medium">Retention Simulator</h1>
        <p className="mt-1 text-sm text-ink-soft">
          A transparent scenario tool (guide section 17) — it does not claim the model proves an intervention will
          work. Every uplift figure here is an assumption you set, not a measured effect.
        </p>
      </div>
      <RetentionSimulator segments={segments} />
    </div>
  );
}
