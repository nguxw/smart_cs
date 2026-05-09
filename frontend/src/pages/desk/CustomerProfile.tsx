import { History, UserRound } from "lucide-react";

import { Card } from "../../components/Card";
import type { CaseTask, SupportCase } from "../../types/api";
import { USERS } from "../../shared/demoData";

export function CustomerProfile({
  userId,
  supportCase,
  task
}: {
  userId: string;
  supportCase: SupportCase | null;
  task: CaseTask | null;
}) {
  const user = USERS.find((item) => item.id === userId) ?? USERS[0];
  return (
    <>
      <Card title="客户上下文" icon={<UserRound />}>
        <div className="profile-stack">
          <strong>{user.name}</strong>
          <span>{user.id} / {user.tier}</span>
          <p>{user.note}</p>
        </div>
      </Card>
      <Card title="当前 Case" icon={<History />}>
        <div className="case-summary">
          <Info label="Case" value={supportCase?.id ?? "未创建"} />
          <Info label="状态" value={supportCase?.status ?? "idle"} />
          <Info label="类别" value={supportCase?.category ?? "-"} />
          <Info label="风险" value={supportCase?.risk_level ?? "low"} />
          <Info label="关联订单" value={supportCase?.related_order_id ?? "-"} />
          <Info label="当前任务" value={task?.required_action ?? "无"} />
        </div>
      </Card>
    </>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="outcome-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
