import { ClipboardCheck, History, RefreshCw, ShieldCheck, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import type { CaseTask, SupportCase, ToolAudit } from "../../types/api";
import type { CaseDetail } from "../../hooks/useCases";
import { formatReadableDateTime } from "../../shared/format";

export function CasesPage({
  cases,
  detail,
  selectedCase,
  onSelectCase,
  onRefresh,
  busy
}: {
  cases: SupportCase[];
  detail: CaseDetail | null;
  selectedCase: SupportCase | null;
  onSelectCase: (caseId: string) => void;
  onRefresh: () => void;
  busy: boolean;
}) {
  const [filter, setFilter] = useState("active");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return cases.filter((supportCase) => {
      const active = !["resolved", "closed"].includes(supportCase.status);
      const matchesFilter =
        filter === "all" ||
        (filter === "active" && active) ||
        supportCase.status === filter ||
        supportCase.priority === filter ||
        supportCase.risk_level === filter;
      const matchesQuery =
        !needle ||
        [
          supportCase.id,
          supportCase.user_id,
          supportCase.category,
          supportCase.summary,
          supportCase.related_order_id,
          supportCase.related_ticket_id
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(needle));
      return matchesFilter && matchesQuery;
    });
  }, [cases, filter, query]);

  return (
    <section className="case-ops-grid">
      <aside className="queue-tabs case-filters" aria-label="服务案件筛选">
        {[
          ["active", "处理中"],
          ["waiting_customer", "待客户确认"],
          ["handoff", "人工接管"],
          ["high", "高风险"],
          ["resolved", "已解决"],
          ["all", "全部"]
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={filter === key ? "active" : ""}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </aside>

      <Card className="case-ledger">
        <div className="section-head compact-head flush-head">
          <div className="section-title">
            <span>
              <ClipboardCheck />
            </span>
            <div>
              <h2>服务案件台账</h2>
              <p>{filtered.length} 个服务案件，按状态、风险、任务和审计证据处理。</p>
            </div>
          </div>
          <button className="icon-button" type="button" aria-label="刷新服务案件" onClick={onRefresh}>
            <RefreshCw className={busy ? "spin" : ""} size={18} />
          </button>
        </div>
        <label className="filter-input">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索服务案件、客户、订单、工单或摘要"
          />
        </label>
        <div className="case-list">
          {filtered.map((supportCase) => (
            <button
              key={supportCase.id}
              type="button"
              className={
                supportCase.id === selectedCase?.id ? "case-row selected" : "case-row"
              }
              onClick={() => onSelectCase(supportCase.id)}
            >
              <span>
                <strong>{supportCase.id}</strong>
                <em>{supportCase.category} / {supportCase.user_id}</em>
                <small>{supportCase.summary || "暂无摘要"}</small>
              </span>
              <b className={`priority ${supportCase.priority}`}>{supportCase.priority}</b>
              <small className={`status ${supportCase.status}`}>{supportCase.status}</small>
            </button>
          ))}
          {filtered.length === 0 && <EmptyState text="没有匹配的服务案件" />}
        </div>
      </Card>

      <Card className="case-detail">
        {selectedCase ? (
          <>
            <div className="detail-head case-detail-head">
              <div>
                <span>当前服务案件</span>
                <h2>{selectedCase.id}</h2>
              </div>
              <Badge tone={selectedCase.risk_level === "high" ? "red" : "blue"}>
                {selectedCase.status}
              </Badge>
            </div>
            <div className="case-facts">
              <Fact label="客户" value={selectedCase.user_id} />
              <Fact label="租户" value={selectedCase.tenant_id} />
              <Fact label="订单" value={selectedCase.related_order_id ?? "-"} />
              <Fact label="工单" value={selectedCase.related_ticket_id ?? "-"} />
              <Fact label="风险" value={selectedCase.risk_level ?? "low"} />
              <Fact label="渠道" value={selectedCase.source_channel} />
            </div>
            <section className="case-thread">
              <ThreadBlock
                icon={<Workflow />}
                title="处理任务"
                emptyText="暂无任务"
                rows={(detail?.tasks ?? []).map((task) => taskToRow(task))}
              />
              <ThreadBlock
                icon={<ShieldCheck />}
                title="工具审计"
                emptyText="暂无工具审计"
                rows={(detail?.audits ?? []).map((audit) => auditToRow(audit))}
              />
              <ThreadBlock
                icon={<History />}
                title="处理结果"
                emptyText="尚未形成结案结果"
                rows={
                  selectedCase.resolution
                    ? [
                        {
                          key: "resolution",
                          title: selectedCase.resolution,
                          meta: formatReadableDateTime(selectedCase.updated_at),
                          tone: "green"
                        }
                      ]
                    : []
                }
              />
            </section>
          </>
        ) : (
          <EmptyState text="请选择一个服务案件" />
        )}
      </Card>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="outcome-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ThreadBlock({
  icon,
  title,
  emptyText,
  rows
}: {
  icon: ReactNode;
  title: string;
  emptyText: string;
  rows: Array<{ key: string; title: string; meta: string; tone: string }>;
}) {
  return (
    <div className="thread-block">
      <div className="thread-title">
        {icon}
        <strong>{title}</strong>
      </div>
      <div className="thread-list">
        {rows.map((row) => (
          <article key={row.key} className="thread-row">
            <span className={`status-chip ${row.tone}`}>{row.meta}</span>
            <strong>{row.title}</strong>
          </article>
        ))}
        {rows.length === 0 && <EmptyState text={emptyText} />}
      </div>
    </div>
  );
}

function taskToRow(task: CaseTask) {
  return {
    key: task.id,
    title: `${task.required_action} / ${task.type}`,
    meta: task.status,
    tone: task.status === "pending" ? "amber" : task.status === "completed" ? "green" : "red"
  };
}

function auditToRow(audit: ToolAudit) {
  return {
    key: audit.id,
    title: `${audit.tool_name} / ${audit.policy_status}`,
    meta: audit.success ? "success" : audit.requires_confirmation ? "confirm" : "blocked",
    tone: audit.success ? "green" : audit.requires_confirmation ? "amber" : "red"
  };
}
