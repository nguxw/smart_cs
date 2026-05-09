import { TerminalSquare } from "lucide-react";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { JsonViewer } from "../../components/JsonViewer";
import type { ToolCall } from "../../types/api";

export function ToolTracePanel({ toolCalls }: { toolCalls: ToolCall[] }) {
  return (
    <Card title="工具与审计" icon={<TerminalSquare />}>
      <div className="tool-list">
        {toolCalls.length === 0 && <EmptyState text="暂无业务工具调用" />}
        {toolCalls.map((call, index) => (
          <article key={`${call.name}-${index}`} className="tool-card">
            <div className="tool-row">
              <div>
                <strong>{labelTool(call.name)}</strong>
                <span>
                  {call.name} / {Math.round(call.duration_ms ?? 0)}ms /{" "}
                  {call.policy_status ?? "unchecked"}
                </span>
              </div>
              <small className={`status ${call.success ? "resolved" : "pending"}`}>
                {call.success ? "success" : "blocked"}
              </small>
            </div>
            <details>
              <summary>参数、返回与审计</summary>
              <JsonViewer
                value={{
                  audit_id: call.audit_id,
                  idempotency_key: call.idempotency_key,
                  arguments: call.arguments,
                  result: call.result,
                  error: call.error
                }}
              />
            </details>
          </article>
        ))}
      </div>
    </Card>
  );
}

function labelTool(name: string) {
  const labels: Record<string, string> = {
    query_order: "订单核验",
    check_refund_eligibility: "退款资格",
    create_refund: "创建退款",
    query_invoice: "发票查询",
    create_ticket: "创建工单",
    handoff_to_human: "人工接管"
  };
  return labels[name] ?? name;
}
