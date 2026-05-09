import type { AgentStep } from "../types/api";
import { EmptyState } from "./EmptyState";

export function Timeline({ steps }: { steps: AgentStep[] }) {
  return (
    <div className="timeline">
      {steps.length === 0 && <EmptyState text="暂无链路事件" />}
      {steps.map((step, index) => (
        <div key={`${step.agent}-${index}`} className={`timeline-row ${step.status}`}>
          <span>{labelAgent(step.agent)}</span>
          <strong>{businessMessage(step.message)}</strong>
          <em>{Math.round(step.elapsed_ms ?? 0)}ms</em>
        </div>
      ))}
    </div>
  );
}

function labelAgent(agent: string) {
  const labels: Record<string, string> = {
    router: "识别意图",
    input_policy: "输入安全",
    case_binding: "绑定Case",
    retrieve_policy: "检索知识",
    tool_policy: "业务工具",
    human_confirm: "用户确认",
    human_handoff: "人工接管",
    guardrail: "输出安全",
    compose_answer: "生成回复",
    memory_writer: "写入记忆"
  };
  return labels[agent] ?? agent;
}

function businessMessage(message: string) {
  return message
    .replace("intent=", "识别为 ")
    .replace("output_safe", "安全检查通过")
    .replace("input_safe", "输入安全")
    .replace("retrieved=", "命中知识 ");
}
