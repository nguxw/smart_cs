import { CheckCircle2, ShieldCheck, TicketCheck, XCircle } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import type { CaseTask, PendingConfirmation, ToolCall } from "../../types/api";
import { buildBusinessOutcome } from "../../shared/format";

export function ActionPanel({
  toolCalls,
  task,
  pendingConfirmation,
  busy,
  onApprove
}: {
  toolCalls: ToolCall[];
  task: CaseTask | null;
  pendingConfirmation: PendingConfirmation | null;
  busy: boolean;
  onApprove: (approved: boolean) => Promise<unknown>;
}) {
  const outcome = buildBusinessOutcome(toolCalls);
  const hasPending = Boolean(task?.status === "pending" || pendingConfirmation);
  return (
    <Card title="处理动作" icon={<TicketCheck />}>
      <div className="action-card">
        <div>
          <span>下一步</span>
          <strong>{hasPending ? "等待用户确认" : outcome.title}</strong>
          <p>{hasPending ? String(pendingConfirmation?.summary ?? "请确认高风险操作。") : outcome.detail}</p>
        </div>
        <Badge tone={hasPending ? "amber" : outcome.tone}>{hasPending ? "confirm" : outcome.status}</Badge>
      </div>

      {hasPending && (
        <div className="decision-row">
          <Button disabled={busy} onClick={() => void onApprove(true)}>
            <CheckCircle2 size={17} />
            确认执行
          </Button>
          <Button tone="danger" disabled={busy} onClick={() => void onApprove(false)}>
            <XCircle size={17} />
            取消
          </Button>
        </div>
      )}

      <div className="risk-strip">
        <ShieldCheck size={16} />
        <span>
          副作用工具必须经过 ToolPolicy、客户确认、幂等键和 ToolAudit 后才会执行。
        </span>
      </div>
    </Card>
  );
}
