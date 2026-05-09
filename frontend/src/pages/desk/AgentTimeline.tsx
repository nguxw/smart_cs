import { Activity } from "lucide-react";

import { Card } from "../../components/Card";
import { Timeline } from "../../components/Timeline";
import type { AgentStep } from "../../types/api";

export function AgentTimeline({ steps }: { steps: AgentStep[] }) {
  return (
    <Card title="可解释执行图" icon={<Activity />}>
      <Timeline steps={steps} />
    </Card>
  );
}
