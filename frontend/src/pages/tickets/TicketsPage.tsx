import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ClipboardList,
  MessageSquare,
  RefreshCw,
  Save,
  Send,
  UserRound
} from "lucide-react";

import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import type { ConversationMessage, Ticket, TicketThread } from "../../types/api";
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS, STATUS_OPTIONS } from "../../shared/demoData";

export function TicketsPage({
  tickets,
  selectedTicket,
  thread,
  threadBusy,
  onSelectTicket,
  onSaveTicket,
  onRefreshThread,
  onOpenConversation,
  onRefresh,
  busy
}: {
  tickets: Ticket[];
  selectedTicket: Ticket | null;
  thread: TicketThread | null;
  threadBusy: boolean;
  onSelectTicket: (ticketId: string) => void;
  onSaveTicket: (ticketId: string, payload: Partial<Ticket>) => Promise<unknown>;
  onRefreshThread: () => void;
  onOpenConversation: (conversationId: string, userId: string) => void;
  onRefresh: () => void;
  busy: boolean;
}) {
  const [queue, setQueue] = useState("active");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState<Partial<Ticket>>({});
  const [replyDraft, setReplyDraft] = useState("");

  useEffect(() => {
    if (selectedTicket) {
      setDraft(selectedTicket);
      setReplyDraft(selectedTicket.human_reply || selectedTicket.suggested_reply || "");
    }
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

  function editablePayload(): Partial<Ticket> {
    return {
      title: draft.title,
      status: draft.status,
      priority: draft.priority,
      category: draft.category,
      assigned_to: draft.assigned_to,
      assignee_name: draft.assignee_name,
      agent_summary: draft.agent_summary,
      resolution_type: draft.resolution_type,
      closed_reason: draft.closed_reason
    };
  }

  async function saveDraft(event: FormEvent) {
    event.preventDefault();
    if (!selectedTicket) return;
    await onSaveTicket(selectedTicket.id, {
      ...editablePayload(),
      suggested_reply: replyDraft
    });
  }

  async function sendReply() {
    if (!selectedTicket || !replyDraft.trim()) return;
    await onSaveTicket(selectedTicket.id, {
      ...editablePayload(),
      status: draft.status === "resolved" ? "resolved" : "pending",
      human_reply: replyDraft.trim()
    });
  }

  async function resolveTicket() {
    if (!selectedTicket) return;
    const finalReply = replyDraft.trim();
    await onSaveTicket(selectedTicket.id, {
      ...editablePayload(),
      status: "resolved",
      human_reply: finalReply || undefined,
      closed_reason:
        draft.closed_reason || finalReply || draft.resolution_type || "人工处理完成",
      resolution_type: draft.resolution_type || "manual_resolution"
    });
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
              <p>{filtered.length} 条结果，人工回复可回写关联会话。</p>
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
          <form className="operation-form ticket-editor" onSubmit={saveDraft}>
            <div className="detail-head workbench-head">
              <div>
                <span>处理台</span>
                <h2>{selectedTicket.id}</h2>
              </div>
              <Badge tone={selectedTicket.priority === "high" ? "red" : "amber"}>
                SLA {selectedTicket.sla_deadline ?? "未设置"}
              </Badge>
            </div>
            <div className="decision-row action-toolbar">
              <Button onClick={() => void quickPatch({ assigned_to: "agent-demo", assignee_name: "Demo Agent" })}>
                <UserRound size={17} />
                接单
              </Button>
              <Button tone="subtle" onClick={() => void quickPatch({ assigned_to: "tier2", assignee_name: "二线支持" })}>
                转派二线
              </Button>
            </div>
            <div className="form-section">
              <label>
                <span>标题</span>
                <input value={draft.title ?? ""} onChange={(event) => setDraft((item) => ({ ...item, title: event.target.value }))} />
              </label>
              <div className="form-grid">
                <Select label="状态" value={draft.status ?? "open"} values={STATUS_OPTIONS} onChange={(value) => setDraft((item) => ({ ...item, status: value }))} />
                <Select label="优先级" value={draft.priority ?? "medium"} values={PRIORITY_OPTIONS} onChange={(value) => setDraft((item) => ({ ...item, priority: value }))} />
                <Select label="类别" value={draft.category ?? "general"} values={CATEGORY_OPTIONS} onChange={(value) => setDraft((item) => ({ ...item, category: value }))} />
                <label>
                  <span>处理人</span>
                  <input value={draft.assignee_name ?? ""} onChange={(event) => setDraft((item) => ({ ...item, assignee_name: event.target.value }))} />
                </label>
              </div>
            </div>
            <div className="form-section ticket-summary-section">
              <label>
                <span>Agent 摘要</span>
                <textarea value={draft.agent_summary ?? draft.description ?? ""} onChange={(event) => setDraft((item) => ({ ...item, agent_summary: event.target.value }))} />
              </label>
            </div>
            <TicketConversationPanel
              thread={thread}
              busy={threadBusy}
              onRefresh={onRefreshThread}
              onOpenConversation={onOpenConversation}
            />
            <div className="form-section ticket-reply-section">
              <label>
                <span>人工回复</span>
                <textarea value={replyDraft} onChange={(event) => setReplyDraft(event.target.value)} />
              </label>
            </div>
            <div className="form-footer">
              <Button tone="subtle" type="submit" disabled={busy}>
                <Save size={17} />
                保存修改
              </Button>
              <Button type="button" disabled={busy || !replyDraft.trim()} onClick={() => void sendReply()}>
                <Send size={17} />
                发送并回写
              </Button>
              <Button tone="danger" type="button" disabled={busy} onClick={() => void resolveTicket()}>
                <CheckCircle2 size={17} />
                结束工单
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

function TicketConversationPanel({
  thread,
  busy,
  onRefresh,
  onOpenConversation
}: {
  thread: TicketThread | null;
  busy: boolean;
  onRefresh: () => void;
  onOpenConversation: (conversationId: string, userId: string) => void;
}) {
  const conversation = thread?.conversation ?? null;
  const messages = conversation?.messages.slice(-10) ?? [];
  return (
    <section className="ticket-thread-panel" aria-label="关联客户会话">
      <div className="ticket-thread-head">
        <div>
          <span>关联会话</span>
          <strong>{conversation?.id ?? "未关联"}</strong>
        </div>
        <div className="ticket-thread-actions">
          <button
            className="icon-button"
            type="button"
            aria-label="刷新关联会话"
            onClick={onRefresh}
            disabled={busy}
          >
            <RefreshCw className={busy ? "spin" : ""} size={17} />
          </button>
          <Button
            tone="subtle"
            disabled={!conversation}
            onClick={() => {
              if (conversation) onOpenConversation(conversation.id, conversation.user_id);
            }}
          >
            <MessageSquare size={17} />
            打开会话
          </Button>
        </div>
      </div>
      <div className="ticket-thread-list">
        {messages.map((message, index) => (
          <article
            key={`${message.role}-${message.created_at ?? index}-${index}`}
            className={`ticket-thread-message ${message.role}`}
          >
            <span>{roleLabel(message)}</span>
            <p>{message.content}</p>
          </article>
        ))}
        {messages.length === 0 && (
          <EmptyState text={conversation ? "暂无会话消息" : "该工单尚未关联会话"} />
        )}
      </div>
    </section>
  );
}

function roleLabel(message: ConversationMessage) {
  if (message.role === "user") return "客户";
  if (message.role === "assistant") return "坐席";
  return "系统";
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
      <span>{label}</span>
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
