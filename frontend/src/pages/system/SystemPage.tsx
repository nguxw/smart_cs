import { Database, GitBranch, Layers3, RefreshCw, Wrench } from "lucide-react";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import type { GraphMetadata, HarnessManifest, Health, ToolSpec } from "../../types/api";
import { formatEdge } from "../../shared/format";

export function SystemPage({
  health,
  graph,
  harness,
  tools,
  busy,
  onRefresh
}: {
  health: Health | null;
  graph: GraphMetadata | null;
  harness: HarnessManifest | null;
  tools: ToolSpec[];
  busy: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="system-grid agentops">
      <Card className="system-health">
        <div className="section-head compact-head">
          <div className="section-title">
            <span>
              <Database />
            </span>
            <div>
              <h2>运行治理</h2>
              <p>API、DB、Redis、Qdrant、LLM、工作流规格与工具审计。</p>
            </div>
          </div>
          <button className="icon-button" type="button" aria-label="刷新系统元数据" onClick={onRefresh}>
            <RefreshCw className={busy ? "spin" : ""} size={18} />
          </button>
        </div>
        <div className="health-grid">
          <Info label="API" value={health?.status ?? "offline"} />
          <Info label="LLM" value={health?.llm_model ?? "-"} />
          <Info label="PostgreSQL" value={health?.repository_backend ?? "-"} />
          <Info label="Redis" value={health?.runtime_backend ?? "-"} />
          <Info label="Qdrant" value={health?.knowledge_backend ?? "-"} />
          <Info label="Collection" value={health?.qdrant_collection ?? "-"} />
        </div>
      </Card>

      <Card title="工作流规格" icon={<GitBranch />} className="graph-panel">
        <div className="runtime-strip">
          <Info label="执行模式" value={graph?.execution_mode ?? "orchestrator_sequence"} />
          <Info label="LangGraph" value={graph?.langgraph_runtime ?? "metadata_only"} />
          <Info label="节点绑定" value={graph?.langgraph_nodes_bound ? "bound" : "not bound"} />
        </div>
        <div className="graph-list">
          {(graph?.nodes ?? []).map((node, index) => (
            <div key={node} className="graph-node">
              <span>{index + 1}</span>
              <strong>{node}</strong>
            </div>
          ))}
        </div>
        <div className="edge-list">
          {(graph?.edges ?? []).map((edge, index) => (
            <span key={`${index}-${formatEdge(edge)}`}>{formatEdge(edge)}</span>
          ))}
        </div>
      </Card>

      <Card title="工具注册中心" icon={<Wrench />} className="tool-registry">
        <div className="registry-grid">
          {tools.map((tool) => (
            <article key={tool.name} className="registry-card">
              <div>
                <strong>{labelTool(tool.name)}</strong>
                <span>{tool.name} / {tool.category ?? "general"}</span>
              </div>
              <p>{tool.description ?? "业务工具"}</p>
            </article>
          ))}
          {tools.length === 0 && <EmptyState text="暂无工具元数据" />}
        </div>
      </Card>

      <Card title="观测入口" icon={<Layers3 />} className="observability-panel">
        <div className="interface-list">
          <Route method="GET" path="/api/cases" detail="Case 队列、状态、风险与当前 Task" />
          <Route method="POST" path="/api/tasks/{id}/confirm" detail="确认 pending task 并执行副作用工具" />
          <Route method="GET" path="/api/tool-audits" detail="工具策略、幂等、审计与错误查询" />
          <Route method="POST" path="/api/evals/run" detail="Agent Regression 与发布门禁" />
          <Route method="GET" path="/api/graph" detail="迁移用图规格、interrupt 节点与 checkpoint 字段" />
        </div>
        <p className="muted">{harness?.definition}</p>
      </Card>
    </section>
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

function Route({ method, path, detail }: { method: string; path: string; detail: string }) {
  return (
    <div className="interface-row">
      <span>{method}</span>
      <strong>{path}</strong>
      <p>{detail}</p>
    </div>
  );
}

function labelTool(name: string) {
  const labels: Record<string, string> = {
    query_order: "订单查询",
    check_refund_eligibility: "退款资格",
    create_refund: "创建退款",
    query_invoice: "发票查询",
    create_ticket: "创建工单",
    handoff_to_human: "人工接管"
  };
  return labels[name] ?? name;
}
