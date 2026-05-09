import type { GraphEdge, ToolCall } from "../types/api";

export function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export function formatScore(value?: number) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

export function formatGateValue(key: string, value: number) {
  if (key.endsWith("_ms") || key.includes("latency")) return `${value}ms`;
  if (key.includes("rate") || key.includes("accuracy") || key.includes("precision")) {
    return `${Math.round(value * 100)}%`;
  }
  return String(value);
}

export function formatEdge(edge: GraphEdge) {
  if (Array.isArray(edge)) return `${edge[0]} -> ${edge[1]}`;
  if (typeof edge === "object") {
    return `${edge.source} -> ${edge.target}${edge.condition ? ` (${edge.condition})` : ""}`;
  }
  return String(edge);
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function buildBusinessOutcome(toolCalls: ToolCall[]) {
  const lastCall = [...toolCalls].reverse().find(Boolean);
  if (!lastCall) {
    return {
      title: "等待处理",
      status: "idle",
      tone: "neutral" as const,
      detail: "当前会话尚未触发业务工具。"
    };
  }
  const result = asRecord(lastCall.result);
  if (lastCall.name === "create_refund") {
    return {
      title: result?.created ? "退款已提交" : "退款未创建",
      status: result?.created ? "submitted" : "blocked",
      tone: result?.created ? ("green" as const) : ("amber" as const),
      detail: String(result?.reason ?? result?.error ?? "退款链路已完成。")
    };
  }
  if (lastCall.name === "check_refund_eligibility") {
    return {
      title: result?.eligible ? "符合自助退款" : "需要人工判断",
      status: result?.eligible ? "eligible" : "not eligible",
      tone: result?.eligible ? ("green" as const) : ("amber" as const),
      detail: String(result?.reason ?? "已完成退款资格校验。")
    };
  }
  if (lastCall.name === "query_invoice") {
    return {
      title: "发票状态",
      status: String(result?.invoice_status ?? "unknown"),
      tone: result?.download_url ? ("green" as const) : ("amber" as const),
      detail: result?.download_url ? "电子发票已生成，可返回下载地址。" : "发票暂不可下载。"
    };
  }
  if (lastCall.name === "query_order") {
    return {
      title: result?.authorized === false ? "权限拦截" : "订单已核验",
      status: result?.authorized === false ? "blocked" : "authorized",
      tone: result?.authorized === false ? ("red" as const) : ("green" as const),
      detail: String(result?.error ?? "订单归属和状态已完成核验。")
    };
  }
  if (lastCall.name === "create_ticket" || lastCall.name === "handoff_to_human") {
    return {
      title: "已进入人工队列",
      status: String(result?.status ?? "open"),
      tone: "blue" as const,
      detail: `工单 ${String(result?.id ?? "已创建")} 已写入客服后台。`
    };
  }
  return {
    title: lastCall.name,
    status: lastCall.success ? "success" : "failed",
    tone: lastCall.success ? ("green" as const) : ("red" as const),
    detail: String(lastCall.error ?? "工具调用完成。")
  };
}
