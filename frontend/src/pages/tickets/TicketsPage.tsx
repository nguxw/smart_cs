import { FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, ClipboardList, RefreshCw, Send, UserRound } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import type { Ticket } from "../../types/api";
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS, STATUS_OPTIONS } from "../../shared/demoData";

export function TicketsPage({
  tickets,
  selectedTicket,
  onSelectTicket,
  onSaveTicket,
  onRefresh,
  busy
}: {
  tickets: Ticket[];
  selectedTicket: Ticket | null;
  onSelectTicket: (ticketId: string) => void;
  onSaveTicket: (ticketId: string, payload: Partial<Ticket>) => Promise<unknown>;
  onRefresh: () => void;
  busy: boolean;
}) {
  const [queue, setQueue] = useState("active");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState<Partial<Ticket>>({});

  useEffect(() => {
    if (selectedTicket) setDraft(selectedTicket);
  }, [selectedTicket]);

  const filtered = useMemo(() => {
    return tickets.filter((ticket) => {
      const matchesQueue =
        queue === "all" ||
        (queue === "active" && ticket.status !== "resolved") ||
        (queue === "mine" && ticket.assigned_to === "agent-demo") ||
        (queue === "sla" && ticket.priority === "high" && ticket.status !== "resolved") ||
        ticket.status === queue ||
        ticket.priority === queue ||
        ticket.category === queue;
      const needle = query.trim().toLowerCase();
      const matchesQuery =
        !needle ||
        [ticket.id, ticket.user_id, ticket.title, ticket.description, ticket.category]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(needle));
      return matchesQueue && matchesQuery;
    });
  }, [query, queue, tickets]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!selectedTicket) return;
    await onSaveTicket(selectedTicket.id, draft);
  }

  async function quickPatch(payload: Partial<Ticket>) {
    if (!selectedTicket) return;
    setDraft((current) => ({ ...current, ...payload }));
    await onSaveTicket(selectedTicket.id, payload);
  }

  return (
    <section className="agent-queue-grid">
      <aside className="queue-tabs">
        {[
          ["active", "全部待处理"],
          ["open", "待分配"],
          ["mine", "我的工单"],
          ["sla", "超时风险"],
          ["high", "高优先级"],
          ["resolved", "已解决"]
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={queue === key ? "active" : ""}
            onClick={() => setQueue(key)}
          >
            {label}
          </button>
        ))}
      </aside>

      <Card className="ticket-queue">
        <div className="section-head compact-head">
          <div className="section-title">
            <span>
              <ClipboardList />
            </span>
            <div>
              <h2>坐席队列</h2>
              <p>{filtered.length} 条结果，按 SLA、优先级和处理人筛选。</p>
            </div>
          </div>
          <button className="icon-button" type="button" aria-label="刷新工单" onClick={onRefresh}>
            <RefreshCw size={18} />
          </button>
        </div>
        <label className="filter-input">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索工单、用户、类别" />
        </label>
        <div className="ticket-list">
          {filtered.map((ticket) => (
            <button
              key={ticket.id}
              type="button"
              className={ticket.id === selectedTicket?.id ? "ticket-row selected" : "ticket-row"}
              onClick={() => onSelectTicket(ticket.id)}
            >
              <span>
                <strong>{ticket.title}</strong>
                <em>{ticket.id} / {ticket.user_id}</em>
                <small>{ticket.latest_customer_message || ticket.description}</small>
              </span>
              <b className={`priority ${ticket.priority}`}>{ticket.priority}</b>
              <small className={`status ${ticket.status}`}>{ticket.status}</small>
            </button>
          ))}
          {filtered.length === 0 && <EmptyState text="没有匹配工单" />}
        </div>
      </Card>

      <Card className="ticket-workbench">
        {selectedTicket ? (
          <form onSubmit={save}>
            <div className="detail-head">
              <div>
                <span>处理台</span>
                <h2>{selectedTicket.id}</h2>
              </div>
              <Badge tone={selectedTicket.priority === "high" ? "red" : "amber"}>
                SLA {selectedTicket.sla_deadline ?? "未设置"}
              </Badge>
            </div>
            <div className="decision-row">
              <Button onClick={() => void quickPatch({ assigned_to: "agent-demo", assignee_name: "Demo Agent" })}>
                <UserRound size={17} />
                接单
              </Button>
              <Button tone="subtle" onClick={() => void quickPatch({ assigned_to: "tier2", assignee_name: "二线支持" })}>
                转派二线
              </Button>
              <Button tone="subtle" onClick={() => void quickPatch({ status: "resolved", closed_reason: "问题已解决" })}>
                <CheckCircle2 size={17} />
                关闭
              </Button>
            </div>
            <label>
              标题
              <input value={draft.title ?? ""} onChange={(event) => setDraft((item) => ({ ...item, title: event.target.value }))} />
            </label>
            <div className="form-grid">
              <Select label="状态" value={draft.status ?? "open"} values={STATUS_OPTIONS} onChange={(value) => setDraft((item) => ({ ...item, status: value }))} />
              <Select label="优先级" value={draft.priority ?? "medium"} values={PRIORITY_OPTIONS} onChange={(value) => setDraft((item) => ({ ...item, priority: value }))} />
              <Select label="类别" value={draft.category ?? "general"} values={CATEGORY_OPTIONS} onChange={(value) => setDraft((item) => ({ ...item, category: value }))} />
              <label>
                处理人
                <input value={draft.assignee_name ?? ""} onChange={(event) => setDraft((item) => ({ ...item, assignee_name: event.target.value }))} />
              </label>
            </div>
            <label>
              Agent 摘要
              <textarea value={draft.agent_summary ?? draft.description ?? ""} onChange={(event) => setDraft((item) => ({ ...item, agent_summary: event.target.value }))} />
            </label>
            <label>
              推荐回复 / 人工回复
              <textarea value={draft.human_reply ?? draft.suggested_reply ?? ""} onChange={(event) => setDraft((item) => ({ ...item, human_reply: event.target.value }))} />
            </label>
            <div className="decision-row">
              <Button type="submit" disabled={busy}>
                <Send size={17} />
                保存处理
              </Button>
            </div>
          </form>
        ) : (
          <EmptyState text="请选择工单" />
        )}
      </Card>
    </section>
  );
}

function Select({
  label,
  value,
  values,
  onChange
}: {
  label: string;
  value: string;
  values: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {values.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
    </label>
  );
}
