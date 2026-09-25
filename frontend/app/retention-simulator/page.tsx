import { listSegments } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import RetentionSimulator from "@/components/RetentionSimulator";

export default async function RetentionSimulatorPage() {
  const segments = await listSegments();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Retention simulator"
        description="Test a campaign on one segment. The save rate is an assumption you set, not a measured effect, so read every result as what would happen if that uplift held."
      />
      <RetentionSimulator segments={segments} />
    </div>
  );
}
