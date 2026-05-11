import { ListChecks } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import type { ActionPlan } from "../../types/api";

export function ActionPlanPanel({ plan }: { plan: ActionPlan | null }) {
  const risk = plan?.risk_level ?? "low";
  const missingSlots = plan?.missing_slots ?? [];
  const tools = plan?.required_tools ?? [];
  return (
    <Card title="ActionPlan" icon={<ListChecks />}>
      <div className="plan-card">
        <div className="plan-headline">
          <div>
            <span>intent</span>
            <strong>{plan?.intent ?? "idle"}</strong>
          </div>
          <Badge tone={riskTone(risk)}>{risk}</Badge>
        </div>
        <div className="plan-grid">
          <PlanMetric label="confidence" value={plan ? `${Math.round(plan.confidence * 100)}%` : "-"} />
          <PlanMetric label="tools" value={tools.length ? tools.join(", ") : "none"} />
          <PlanMetric label="missing" value={missingSlots.length ? missingSlots.join(", ") : "none"} />
          <PlanMetric
            label="confirmation"
            value={plan?.requires_confirmation ? "required" : "not required"}
          />
        </div>
        <p>{plan?.reason ?? "等待下一轮客户消息生成可审计计划。"}</p>
      </div>
    </Card>
  );
}

function PlanMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function riskTone(risk: string): "red" | "amber" | "green" {
  if (risk === "high") return "red";
  if (risk === "medium") return "amber";
  return "green";
}
