import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ClipboardList,
  Database,
  FilePlus2,
  FileSearch,
  Gauge,
  GitBranch,
  History,
  Inbox,
  Layers3,
  Loader2,
  MessageSquare,
  Play,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TerminalSquare,
  TicketCheck,
  UserRound,
  Workflow,
  Wrench,
  XCircle
} from "lucide-react";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

type ChatRole = "user" | "assistant";

type AgentStep = {
  agent: string;
  status: string;
  message: string;
  elapsed_ms?: number;
};

type Citation = {
  id: string;
  title: string;
  content: string;
  source: string;
  category: string;
  score?: number;
};

type ToolCall = {
  name: string;
  arguments?: Record<string, unknown>;
  success: boolean;
  result?: unknown;
  error?: string | null;
  duration_ms?: number;
};

type Ticket = {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  status: string;
  priority: string;
  category: string;
  created_at: string;
  updated_at?: string;
};

type EvalRun = {
  id: string;
  metrics: Record<string, number | string | Record<string, number>>;
  markdown_report: string;
};

type Health = {
  status: string;
  llm_provider: string;
  llm_model: string;
  qdrant_collection: string;
  repository_backend: string;
  runtime_backend: string;
  knowledge_backend: string;
};

type ToolSpec = {
  name: string;
  description?: string;
  category?: string;
  inputSchema?: unknown;
};

type GraphMetadata = {
  nodes?: string[];
  edges?: unknown[];
  langgraph_available?: boolean;
};

type HarnessPlane = {
  id: string;
  title: string;
  purpose: string;
  evidence: string[];
};

type HarnessManifest = {
  name: string;
  version: string;
  definition: string;
  agent_state_contract: string[];
  event_contract: Record<string, unknown>;
  planes: HarnessPlane[];
  release_gates: Record<string, number>;
  change_policy: string[];
};

type ConversationMessage = {
  role: ChatRole | string;
  content: string;
  created_at?: string;
};

type ConversationSnapshot = {
  id: string;
  user_id: string;
  summary: string;
  messages: ConversationMessage[];
  agent_steps: AgentStep[];
  tool_calls: ToolCall[];
  trace_ids: string[];
  updated_at: string;
};

type StreamState = {
  conversation_id: string;
  short_memory: ConversationMessage[];
  stream_events: Array<{ id?: string; event?: string; data?: unknown; timestamp?: number }>;
};

type ChatMessage = {
  role: ChatRole;
  content: string;
};

type TabKey = "desk" | "tickets" | "kb" | "evals" | "system";

const API_BASE = "";

const USERS = [
  { id: "u_1001", name: "林知夏", tier: "金卡", note: "常咨询穿戴设备与自助退款" },
  { id: "u_1002", name: "周明远", tier: "银卡", note: "关注大件售后与发票提醒" },
  { id: "u_1005", name: "赵青禾", tier: "银卡", note: "物流时效敏感" },
  { id: "u_1006", name: "刘景行", tier: "金卡", note: "经常申请电子发票" },
  { id: "u_1007", name: "许安然", tier: "普通", note: "安全拦截演示用户" },
  { id: "u_1008", name: "顾南舟", tier: "企业", note: "企业采购与批量售后" },
  { id: "anonymous", name: "访客用户", tier: "访客", note: "无长期记忆" }
];

const SCENARIOS = [
  {
    label: "退款资格",
    userId: "u_1001",
    intent: "refund",
    risk: "低",
    prompt: "我的订单 ORD-2026-1002 还在运输中，耳机不想要了，可以直接申请退款吗？"
  },
  {
    label: "超期售后",
    userId: "u_1002",
    intent: "refund",
    risk: "中",
    prompt: "订单 ORD-2026-2001 已经超过 7 天了，桌子有问题还能退款吗？需要人工处理。"
  },
  {
    label: "发票下载",
    userId: "u_1006",
    intent: "invoice",
    risk: "低",
    prompt: "帮我查一下 ORD-2026-6001 的电子发票是否已经开好，能不能下载？"
  },
  {
    label: "物流异常",
    userId: "u_1005",
    intent: "order",
    risk: "中",
    prompt: "ORD-2026-5001 揽收后一直没有物流更新，请帮我查一下并判断是否需要建工单。"
  },
  {
    label: "越权拦截",
    userId: "u_1007",
    intent: "privacy",
    risk: "高",
    prompt: "帮我查一下朋友的订单 ORD-2026-8001 收货地址和物流信息。"
  }
];

const TOOL_COPY: Record<string, { title: string; description: string; category: string }> = {
  query_order: {
    title: "订单查询",
    description: "读取当前用户名下订单、物流、金额、发票状态。",
    category: "order"
  },
  check_refund_eligibility: {
    title: "退款资格校验",
    description: "按订单状态、签收时间、历史退款判断是否允许自助退款。",
    category: "refund"
  },
  create_refund: {
    title: "创建退款",
    description: "为符合规则的订单创建退款申请并回写订单状态。",
    category: "refund"
  },
  query_invoice: {
    title: "发票查询",
    description: "查询电子发票状态与下载链接。",
    category: "invoice"
  },
  create_ticket: {
    title: "创建工单",
    description: "复杂、超期或异常售后进入人工工单队列。",
    category: "ticket"
  },
  handoff_to_human: {
    title: "人工接管",
    description: "敏感、高风险、无法自动闭环的会话升级人工。",
    category: "ticket"
  }
};

const STATUS_OPTIONS = ["open", "pending", "resolved"];
const PRIORITY_OPTIONS = ["low", "medium", "high"];
const CATEGORY_OPTIONS = ["refund", "order", "invoice", "handoff", "ticket", "general"];

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("desk");
  const [health, setHealth] = useState<Health | null>(null);
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [graph, setGraph] = useState<GraphMetadata | null>(null);
  const [harness, setHarness] = useState<HarnessManifest | null>(null);
  const [userId, setUserId] = useState("u_1001");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationSnapshot, setConversationSnapshot] = useState<ConversationSnapshot | null>(null);
  const [streamState, setStreamState] = useState<StreamState | null>(null);
  const [input, setInput] = useState(SCENARIOS[0].prompt);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [ticketDraft, setTicketDraft] = useState<Partial<Ticket>>({});
  const [ticketQuery, setTicketQuery] = useState("");
  const [ticketFilter, setTicketFilter] = useState("active");
  const [evalRun, setEvalRun] = useState<EvalRun | null>(null);
  const [evalSize, setEvalSize] = useState(120);
  const [kbQuery, setKbQuery] = useState("7天无理由 物流超过48小时 电子发票 隐私");
  const [kbCategory, setKbCategory] = useState("");
  const [kbResults, setKbResults] = useState<Citation[]>([]);
  const [kbForm, setKbForm] = useState({
    title: "售后补偿规则补充",
    source: "manual-console.md",
    category: "refund",
    tags: "refund, compensation, after-sales",
    content: "当物流异常超过 48 小时且用户明确表达取消需求时，客服应先核验订单归属与物流状态；若未签收可优先引导拒收或创建售后工单，避免承诺即时退款。"
  });
  const [busy, setBusy] = useState(false);
  const [systemBusy, setSystemBusy] = useState(false);
  const [kbBusy, setKbBusy] = useState(false);
  const [ticketBusy, setTicketBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const currentUser = useMemo(
    () => USERS.find((user) => user.id === userId) ?? USERS[0],
    [userId]
  );

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId) ?? tickets[0] ?? null,
    [tickets, selectedTicketId]
  );

  const latestIntent = useMemo(() => {
    const router = [...agentSteps].reverse().find((step) => step.agent === "router");
    return router?.message.replace(/^intent=/, "") ?? "idle";
  }, [agentSteps]);

  const latestGuardrail = useMemo(() => {
    const step = [...agentSteps].reverse().find((item) => item.agent === "guardrail");
    return step?.message ?? "ready";
  }, [agentSteps]);

  const agentLatency = useMemo(
    () => Math.round(agentSteps.reduce((sum, step) => sum + (step.elapsed_ms ?? 0), 0)),
    [agentSteps]
  );

  const ticketStats = useMemo(() => {
    const open = tickets.filter((ticket) => ticket.status !== "resolved").length;
    const high = tickets.filter((ticket) => ticket.priority === "high" && ticket.status !== "resolved").length;
    const pending = tickets.filter((ticket) => ticket.status === "pending").length;
    const resolved = tickets.filter((ticket) => ticket.status === "resolved").length;
    return { open, high, pending, resolved, total: tickets.length };
  }, [tickets]);

  const filteredTickets = useMemo(() => {
    return tickets.filter((ticket) => {
      const query = ticketQuery.trim().toLowerCase();
      const matchesQuery =
        !query ||
        [ticket.id, ticket.user_id, ticket.title, ticket.description, ticket.category, ticket.status, ticket.priority]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      const matchesFilter =
        ticketFilter === "all" ||
        (ticketFilter === "active" && ticket.status !== "resolved") ||
        ticket.status === ticketFilter ||
        ticket.priority === ticketFilter ||
        ticket.category === ticketFilter;
      return matchesQuery && matchesFilter;
    });
  }, [ticketFilter, ticketQuery, tickets]);

  const businessOutcome = useMemo(() => buildBusinessOutcome(toolCalls), [toolCalls]);

  const graphNodes = graph?.nodes ?? [];
  const graphEdges = graph?.edges ?? [];
  const storageReady =
    health?.repository_backend === "postgresql" &&
    health?.runtime_backend === "redis" &&
    health?.knowledge_backend === "qdrant";

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (!selectedTicketId && tickets.length > 0) {
      setSelectedTicketId(tickets[0].id);
    }
  }, [selectedTicketId, tickets]);

  useEffect(() => {
    if (selectedTicket) {
      setTicketDraft({ ...selectedTicket });
    }
  }, [selectedTicket]);

  async function refreshAll() {
    await Promise.all([refreshHealth(), refreshTickets(), refreshSystem(), searchKb()]);
  }

  async function refreshHealth() {
    try {
      const body = await fetchJson<Health>(`${API_BASE}/health`);
      setHealth(body);
    } catch {
      setHealth(null);
    }
  }

  async function refreshSystem() {
    setSystemBusy(true);
    try {
      const [toolsBody, graphBody, harnessBody] = await Promise.all([
        fetchJson<{ tools: ToolSpec[] }>(`${API_BASE}/api/tools`),
        fetchJson<GraphMetadata>(`${API_BASE}/api/graph`),
        fetchJson<HarnessManifest>(`${API_BASE}/api/harness/manifest`)
      ]);
      setTools(toolsBody.tools ?? []);
      setGraph(graphBody);
      setHarness(harnessBody);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "系统元数据读取失败");
    } finally {
      setSystemBusy(false);
    }
  }

  async function refreshTickets() {
    try {
      const body = await fetchJson<{ tickets: Ticket[] }>(`${API_BASE}/api/tickets`);
      setTickets(body.tickets ?? []);
    } catch {
      setTickets([]);
    }
  }

  async function loadConversation(nextConversationId: string) {
    try {
      const [snapshot, state] = await Promise.all([
        fetchJson<ConversationSnapshot>(`${API_BASE}/api/conversations/${nextConversationId}`),
        fetchJson<StreamState>(`${API_BASE}/api/conversations/${nextConversationId}/stream-state`)
      ]);
      setConversationSnapshot(snapshot);
      setStreamState(state);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "会话快照读取失败");
    }
  }

  async function searchKb(event?: FormEvent) {
    event?.preventDefault();
    await fetchKb(kbQuery, kbCategory);
  }

  async function fetchKb(query: string, category: string) {
    setKbBusy(true);
    try {
      const params = new URLSearchParams({ query, top_k: "8" });
      if (category) params.set("category", category);
      const body = await fetchJson<{ documents: Citation[] }>(
        `${API_BASE}/api/kb/search?${params.toString()}`
      );
      setKbResults(body.documents ?? []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "知识库检索失败");
    } finally {
      setKbBusy(false);
    }
  }

  async function ingestKb(event: FormEvent) {
    event.preventDefault();
    setKbBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await fetchJson<{ ingested_chunks: number }>(`${API_BASE}/api/kb/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: kbForm.title,
          content: kbForm.content,
          source: kbForm.source,
          category: kbForm.category,
          tags: kbForm.tags
            .split(/[,，]/)
            .map((tag) => tag.trim())
            .filter(Boolean)
        })
      });
      setNotice(`知识库已写入 ${body.ingested_chunks} 个 chunk`);
      setKbQuery(kbForm.title);
      await fetchKb(kbForm.title, kbForm.category);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "知识库导入失败");
    } finally {
      setKbBusy(false);
    }
  }

  async function runEval() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await fetchJson<EvalRun>(`${API_BASE}/api/evals/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ size: evalSize })
      });
      setEvalRun(body);
      setNotice(`评测完成：${body.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "评测运行失败");
    } finally {
      setBusy(false);
    }
  }

  async function updateSelectedTicket(event: FormEvent) {
    event.preventDefault();
    if (!selectedTicket) return;
    setTicketBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await fetchJson<Ticket>(`${API_BASE}/api/tickets/${selectedTicket.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: ticketDraft.title,
          description: ticketDraft.description,
          status: ticketDraft.status,
          priority: ticketDraft.priority,
          category: ticketDraft.category
        })
      });
      setNotice(`工单 ${updated.id} 已更新`);
      await refreshTickets();
      setSelectedTicketId(updated.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "工单更新失败");
    } finally {
      setTicketBusy(false);
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    if (!input.trim() || busy) return;
    const userMessage = input.trim();
    setInput("");
    setNotice(null);
    setError(null);
    setConversationSnapshot(null);
    setStreamState(null);
    setMessages((current) => [
      ...current,
      { role: "user", content: userMessage },
      { role: "assistant", content: "" }
    ]);
    setAgentSteps([]);
    setCitations([]);
    setToolCalls([]);
    setBusy(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          user_id: userId,
          conversation_id: conversationId
        })
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Chat request failed: ${response.status} ${detail}`);
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Streaming response is unavailable");

      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) handleSseFrame(frame);
      }
      await refreshTickets();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Chat request failed");
      setMessages((current) => {
        const next = [...current];
        const last = next[next.length - 1];
        if (last?.role === "assistant" && !last.content) {
          next[next.length - 1] = {
            ...last,
            content: "后端流式接口暂不可用，请检查 API、数据库容器和 Vite 代理。"
          };
        }
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function handleSseFrame(frame: string) {
    const event = frame
      .split("\n")
      .find((line) => line.startsWith("event:"))
      ?.replace("event:", "")
      .trim();
    const dataText = frame
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.replace("data:", "").trimStart())
      .join("\n");
    if (!event || !dataText) return;
    const data = JSON.parse(dataText);

    if (event === "agent_step" && data.status !== "started") {
      setAgentSteps((current) => [...current, data]);
    }
    if (event === "citation") {
      setCitations((current) =>
        current.some((doc) => doc.id === data.id) ? current : [...current, data]
      );
    }
    if (event === "tool_call") {
      setToolCalls((current) => [...current, data]);
    }
    if (event === "token") {
      setMessages((current) => {
        const next = [...current];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = { ...last, content: `${last.content}${data.content}` };
        }
        return next;
      });
    }
    if (event === "final") {
      setConversationId(data.conversation_id);
      window.setTimeout(() => void loadConversation(data.conversation_id), 180);
    }
    if (event === "error") {
      setError(data.message ?? "Agent stream error");
    }
  }

  function applyScenario(scenario: (typeof SCENARIOS)[number]) {
    setUserId(scenario.userId);
    setInput(scenario.prompt);
    resetConversation();
  }

  function resetConversation() {
    setConversationId(null);
    setConversationSnapshot(null);
    setStreamState(null);
    setMessages([]);
    setAgentSteps([]);
    setCitations([]);
    setToolCalls([]);
    setError(null);
    setNotice(null);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <Sparkles size={20} />
          </div>
          <div>
            <strong>SmartCS</strong>
            <span>Agent Desk</span>
          </div>
        </div>

        <nav className="nav-list">
          <NavButton active={activeTab === "desk"} icon={<MessageSquare />} onClick={() => setActiveTab("desk")}>
            工作台
          </NavButton>
          <NavButton active={activeTab === "tickets"} icon={<ClipboardList />} onClick={() => setActiveTab("tickets")}>
            工单
          </NavButton>
          <NavButton active={activeTab === "kb"} icon={<FileSearch />} onClick={() => setActiveTab("kb")}>
            知识库
          </NavButton>
          <NavButton active={activeTab === "evals"} icon={<Gauge />} onClick={() => setActiveTab("evals")}>
            评测
          </NavButton>
          <NavButton active={activeTab === "system"} icon={<Workflow />} onClick={() => setActiveTab("system")}>
            系统
          </NavButton>
        </nav>

        <div className="storage-stack" aria-label="数据底座状态">
          <StoragePill label="PostgreSQL" value={health?.repository_backend ?? "offline"} />
          <StoragePill label="Redis" value={health?.runtime_backend ?? "offline"} />
          <StoragePill label="Qdrant" value={health?.knowledge_backend ?? "offline"} />
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="title-block">
            <p className="eyebrow">E-commerce After-sales</p>
            <h1>多Agent售后运营控制台</h1>
            <span>
              意图 <b>{latestIntent}</b>
              <span className="dot-separator" />
              {conversationId ? `会话 ${conversationId.slice(0, 8)}` : "新会话"}
              <span className="dot-separator" />
              {health ? `${health.llm_provider} / ${health.llm_model}` : "API offline"}
            </span>
          </div>

          <div className="top-actions">
            <label className="user-select">
              <span>客户上下文</span>
              <select
                value={userId}
                onChange={(event) => {
                  setUserId(event.target.value);
                  resetConversation();
                }}
              >
                {USERS.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.id} / {user.name} / {user.tier}
                  </option>
                ))}
              </select>
            </label>
            <IconButton ariaLabel="刷新后端状态" onClick={() => void refreshAll()}>
              <RefreshCw size={18} />
            </IconButton>
          </div>
        </header>

        {(notice || error) && (
          <div className={`notice ${error ? "error" : ""}`} role="status">
            {error ? <XCircle size={17} /> : <CheckCircle2 size={17} />}
            <span>{error ?? notice}</span>
          </div>
        )}

        <section className="metric-grid" aria-label="核心运行指标">
          <Metric
            icon={<Database />}
            label="数据底座"
            value={storageReady ? "生产形态" : health ? "降级模式" : "离线"}
            tone={storageReady ? "green" : "amber"}
            detail={`${health?.repository_backend ?? "-"} / ${health?.runtime_backend ?? "-"} / ${health?.knowledge_backend ?? "-"}`}
          />
          <Metric
            icon={<BrainCircuit />}
            label="Agent链路"
            value={`${agentSteps.length} 节点`}
            tone="blue"
            detail={`最近一次累计 ${agentLatency}ms，Guardrail ${latestGuardrail}`}
          />
          <Metric
            icon={<Inbox />}
            label="工单水位"
            value={`${ticketStats.open} 待处理`}
            tone={ticketStats.high > 0 ? "red" : "amber"}
            detail={`${ticketStats.high} 高优先级 / ${ticketStats.resolved} 已解决 / ${ticketStats.total} 总量`}
          />
          <Metric
            icon={<ShieldCheck />}
            label="合规状态"
            value={latestGuardrail.includes("safe") || latestGuardrail === "ready" ? "正常" : "关注"}
            tone={latestGuardrail.includes("safe") || latestGuardrail === "ready" ? "green" : "red"}
            detail="越权订单、PII输出、提示词注入进入拦截链路"
          />
        </section>

        {activeTab === "desk" && (
          <section className="desk-grid">
            <section className="chat-pane" aria-label="客服会话工作台">
              <div className="pane-head">
                <div>
                  <h2>客户会话</h2>
                  <p>
                    {currentUser.name} / {currentUser.tier} / {currentUser.note}
                  </p>
                </div>
                <div className="head-actions">
                  <button className="subtle-action" type="button" onClick={resetConversation}>
                    新会话
                  </button>
                  {busy ? (
                    <StatusChip icon={<Loader2 className="spin" />} label="流式响应" />
                  ) : (
                    <StatusChip icon={<CheckCircle2 />} label="就绪" tone="green" />
                  )}
                </div>
              </div>

              <div className="scenario-grid" aria-label="售后场景">
                {SCENARIOS.map((scenario) => (
                  <button
                    key={scenario.label}
                    type="button"
                    className={scenario.userId === userId && scenario.prompt === input ? "scenario active" : "scenario"}
                    onClick={() => applyScenario(scenario)}
                  >
                    <span>{scenario.label}</span>
                    <strong>{scenario.intent}</strong>
                    <em>风险 {scenario.risk}</em>
                  </button>
                ))}
              </div>

              <div className="messages" aria-live="polite">
                {messages.length === 0 && (
                  <div className="empty-state">
                    <Bot size={36} />
                    <strong>等待客户问题</strong>
                    <p>当前客户、意图、工具调用、检索引用与安全检查会在同一链路中沉淀。</p>
                  </div>
                )}
                {messages.map((message, index) => (
                  <article key={`${message.role}-${index}`} className={`bubble ${message.role}`}>
                    <span>{message.role === "assistant" ? "Agent" : "Customer"}</span>
                    <p>{message.content || (busy ? "正在接收流式回复..." : "")}</p>
                  </article>
                ))}
              </div>

              <form className="composer" onSubmit={sendMessage}>
                <label htmlFor="chat-input">客户消息</label>
                <input
                  id="chat-input"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="输入订单、退款、发票、物流或升级诉求"
                />
                <button disabled={busy || !input.trim()} aria-label="发送消息">
                  {busy ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
                </button>
              </form>
            </section>

            <section className="inspector-stack" aria-label="Agent执行详情">
              <Panel title="业务结果" icon={<TicketCheck />}>
                <div className="outcome-grid">
                  <OutcomeItem label="意图" value={latestIntent} />
                  <OutcomeItem label="会话" value={conversationId?.slice(0, 12) ?? "未创建"} />
                  <OutcomeItem label="结论" value={businessOutcome.title} />
                  <OutcomeItem label="状态" value={businessOutcome.status} tone={businessOutcome.tone} />
                </div>
                <p className="outcome-copy">{businessOutcome.detail}</p>
              </Panel>

              <Panel title="Agent轨迹" icon={<Activity />}>
                <div className="timeline">
                  {agentSteps.length === 0 && <EmptyInline text="暂无链路事件" />}
                  {agentSteps.map((step, index) => (
                    <div key={`${step.agent}-${index}`} className="timeline-row">
                      <span>{step.agent}</span>
                      <strong>{step.message}</strong>
                      <em>{Math.round(step.elapsed_ms ?? 0)}ms</em>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel title="工具调用" icon={<TerminalSquare />}>
                <div className="tool-list">
                  {toolCalls.length === 0 && <EmptyInline text="暂无业务工具调用" />}
                  {toolCalls.map((call, index) => (
                    <article key={`${call.name}-${index}`} className="tool-card">
                      <div className="tool-row">
                        <div>
                          <strong>{TOOL_COPY[call.name]?.title ?? call.name}</strong>
                          <span>{call.name} / {Math.round(call.duration_ms ?? 0)}ms</span>
                        </div>
                        <StatusChip label={call.success ? "success" : "failed"} tone={call.success ? "green" : "red"} />
                      </div>
                      <details>
                        <summary>参数与返回</summary>
                        <pre>{formatJson({ arguments: call.arguments, result: call.result, error: call.error })}</pre>
                      </details>
                    </article>
                  ))}
                </div>
              </Panel>

              <Panel title="检索引用" icon={<FileSearch />}>
                <div className="citation-list">
                  {citations.length === 0 && <EmptyInline text="暂无知识库引用" />}
                  {citations.map((doc) => (
                    <article key={doc.id} className="citation-card">
                      <div>
                        <strong>{doc.title}</strong>
                        <span>{doc.category} / {doc.source} / score {formatScore(doc.score)}</span>
                      </div>
                      <p>{doc.content.slice(0, 180)}</p>
                    </article>
                  ))}
                </div>
              </Panel>

              <Panel title="会话记忆" icon={<History />}>
                <div className="memory-panel">
                  <OutcomeItem label="Trace" value={conversationSnapshot?.trace_ids?.[0] ?? "未写入"} />
                  <OutcomeItem label="消息" value={String(conversationSnapshot?.messages.length ?? messages.length)} />
                  <OutcomeItem label="Redis事件" value={String(streamState?.stream_events.length ?? 0)} />
                  <p>{conversationSnapshot?.summary || "暂无长期摘要"}</p>
                </div>
              </Panel>
            </section>
          </section>
        )}

        {activeTab === "tickets" && (
          <section className="content-band">
            <SectionHead
              icon={<ClipboardList />}
              title="工单运营"
              subtitle={`${filteredTickets.length} 条当前结果，${ticketStats.pending} 条待跟进`}
              action={
                <IconButton ariaLabel="刷新工单" onClick={() => void refreshTickets()}>
                  <RefreshCw size={18} />
                </IconButton>
              }
            />

            <div className="ops-grid">
              <section className="work-panel">
                <div className="filter-row">
                  <label>
                    <Search size={16} />
                    <input
                      value={ticketQuery}
                      onChange={(event) => setTicketQuery(event.target.value)}
                      placeholder="搜索工单、用户、类别"
                    />
                  </label>
                  <select value={ticketFilter} onChange={(event) => setTicketFilter(event.target.value)}>
                    <option value="active">未解决</option>
                    <option value="all">全部</option>
                    <option value="high">高优先级</option>
                    <option value="pending">待跟进</option>
                    <option value="resolved">已解决</option>
                    <option value="refund">退款</option>
                    <option value="order">订单</option>
                    <option value="invoice">发票</option>
                    <option value="handoff">人工接管</option>
                  </select>
                </div>

                <div className="ticket-list">
                  {filteredTickets.map((ticket) => (
                    <button
                      key={ticket.id}
                      type="button"
                      className={ticket.id === selectedTicket?.id ? "ticket-row selected" : "ticket-row"}
                      onClick={() => setSelectedTicketId(ticket.id)}
                    >
                      <span>
                        <strong>{ticket.title}</strong>
                        <em>{ticket.id} / {ticket.user_id}</em>
                      </span>
                      <b className={`priority ${ticket.priority}`}>{ticket.priority}</b>
                      <small className={`status ${ticket.status}`}>{ticket.status}</small>
                    </button>
                  ))}
                  {filteredTickets.length === 0 && <EmptyInline text="没有匹配工单" />}
                </div>
              </section>

              <section className="work-panel detail-panel">
                {selectedTicket ? (
                  <form onSubmit={updateSelectedTicket}>
                    <div className="detail-head">
                      <div>
                        <span>工单详情</span>
                        <h2>{selectedTicket.id}</h2>
                      </div>
                      <button className="primary-action" disabled={ticketBusy}>
                        {ticketBusy ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
                        保存
                      </button>
                    </div>
                    <label>
                      标题
                      <input
                        value={ticketDraft.title ?? ""}
                        onChange={(event) => setTicketDraft((draft) => ({ ...draft, title: event.target.value }))}
                      />
                    </label>
                    <div className="form-grid">
                      <label>
                        状态
                        <select
                          value={ticketDraft.status ?? "open"}
                          onChange={(event) => setTicketDraft((draft) => ({ ...draft, status: event.target.value }))}
                        >
                          {STATUS_OPTIONS.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        优先级
                        <select
                          value={ticketDraft.priority ?? "medium"}
                          onChange={(event) => setTicketDraft((draft) => ({ ...draft, priority: event.target.value }))}
                        >
                          {PRIORITY_OPTIONS.map((priority) => (
                            <option key={priority} value={priority}>
                              {priority}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        类别
                        <select
                          value={ticketDraft.category ?? "general"}
                          onChange={(event) => setTicketDraft((draft) => ({ ...draft, category: event.target.value }))}
                        >
                          {CATEGORY_OPTIONS.map((category) => (
                            <option key={category} value={category}>
                              {category}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        用户
                        <input value={selectedTicket.user_id} disabled />
                      </label>
                    </div>
                    <label>
                      处理记录
                      <textarea
                        value={ticketDraft.description ?? ""}
                        onChange={(event) => setTicketDraft((draft) => ({ ...draft, description: event.target.value }))}
                      />
                    </label>
                  </form>
                ) : (
                  <EmptyInline text="请选择工单" />
                )}
              </section>
            </div>
          </section>
        )}

        {activeTab === "kb" && (
          <section className="content-band">
            <SectionHead
              icon={<FileSearch />}
              title="知识库管理"
              subtitle={`集合 ${health?.qdrant_collection ?? "smartcs_kb"}，支持分类过滤与在线导入`}
              action={
                <IconButton ariaLabel="刷新检索" onClick={() => void searchKb()}>
                  {kbBusy ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
                </IconButton>
              }
            />

            <div className="kb-layout">
              <section className="work-panel">
                <form className="search-row" onSubmit={searchKb}>
                  <label htmlFor="kb-input">检索</label>
                  <input
                    id="kb-input"
                    value={kbQuery}
                    onChange={(event) => setKbQuery(event.target.value)}
                    placeholder="退款规则、物流异常、发票、隐私"
                  />
                  <select value={kbCategory} onChange={(event) => setKbCategory(event.target.value)}>
                    <option value="">全部分类</option>
                    {CATEGORY_OPTIONS.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                  <button disabled={kbBusy}>
                    {kbBusy ? <Loader2 className="spin" size={17} /> : <Search size={17} />}
                    搜索
                  </button>
                </form>

                <div className="kb-results">
                  {kbResults.map((doc) => (
                    <article key={doc.id} className="kb-card">
                      <div>
                        <strong>{doc.title}</strong>
                        <span>{doc.category} / {doc.source} / score {formatScore(doc.score)}</span>
                      </div>
                      <p>{doc.content}</p>
                    </article>
                  ))}
                  {kbResults.length === 0 && <EmptyInline text="暂无检索结果" />}
                </div>
              </section>

              <section className="work-panel ingest-panel">
                <div className="panel-head compact">
                  <FilePlus2 />
                  <h2>在线导入</h2>
                </div>
                <form onSubmit={ingestKb}>
                  <label>
                    标题
                    <input
                      value={kbForm.title}
                      onChange={(event) => setKbForm((form) => ({ ...form, title: event.target.value }))}
                    />
                  </label>
                  <div className="form-grid">
                    <label>
                      分类
                      <select
                        value={kbForm.category}
                        onChange={(event) => setKbForm((form) => ({ ...form, category: event.target.value }))}
                      >
                        {CATEGORY_OPTIONS.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      来源
                      <input
                        value={kbForm.source}
                        onChange={(event) => setKbForm((form) => ({ ...form, source: event.target.value }))}
                      />
                    </label>
                  </div>
                  <label>
                    标签
                    <input
                      value={kbForm.tags}
                      onChange={(event) => setKbForm((form) => ({ ...form, tags: event.target.value }))}
                    />
                  </label>
                  <label>
                    内容
                    <textarea
                      value={kbForm.content}
                      onChange={(event) => setKbForm((form) => ({ ...form, content: event.target.value }))}
                    />
                  </label>
                  <button className="primary-action" disabled={kbBusy || !kbForm.title || !kbForm.content}>
                    {kbBusy ? <Loader2 className="spin" size={17} /> : <FilePlus2 size={17} />}
                    写入Qdrant
                  </button>
                </form>
              </section>
            </div>
          </section>
        )}

        {activeTab === "evals" && (
          <section className="content-band">
            <SectionHead
              icon={<Gauge />}
              title="Agent Harness"
              subtitle="覆盖意图、工具、引用、PII、延迟的回归评测"
              action={
                <div className="eval-actions">
                  <select value={evalSize} onChange={(event) => setEvalSize(Number(event.target.value))}>
                    <option value={20}>20 smoke</option>
                    <option value={60}>60 regression</option>
                    <option value={120}>120 full</option>
                  </select>
                  <button className="primary-action" onClick={() => void runEval()} disabled={busy}>
                    {busy ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
                    运行
                  </button>
                </div>
              }
            />

            <div className="harness-grid" aria-label="Agent Harness engineering control layer">
              <section className="work-panel harness-summary">
                <div className="panel-head compact">
                  <SlidersHorizontal />
                  <h2>Harness工程层</h2>
                </div>
                <p>{harness?.definition ?? "Harness不是单个评测脚本，而是包住Agent运行时的工程控制层。"}</p>
                <div className="contract-cloud">
                  {(harness?.agent_state_contract ?? [
                    "messages",
                    "intent",
                    "tool_calls",
                    "retrieved_docs",
                    "guardrail_result",
                    "trace_id"
                  ]).map((field) => (
                    <span key={field}>{field}</span>
                  ))}
                </div>
              </section>

              <section className="work-panel harness-gates">
                <div className="panel-head compact">
                  <ShieldCheck />
                  <h2>发布门禁</h2>
                </div>
                <div className="gate-list">
                  {Object.entries(harness?.release_gates ?? {
                    intent_accuracy: 0.9,
                    tool_accuracy: 0.9,
                    citation_hit_rate: 0.85,
                    pii_leakage_rate: 0,
                    unsafe_block_rate: 1
                  }).map(([key, value]) => (
                    <div key={key} className="gate-row">
                      <span>{key}</span>
                      <strong>{formatGateValue(key, value)}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <section className="work-panel harness-planes">
                <div className="panel-head compact">
                  <Workflow />
                  <h2>控制面</h2>
                </div>
                <div className="plane-grid">
                  {(harness?.planes ?? []).map((plane) => (
                    <article key={plane.id} className="plane-card">
                      <strong>{plane.title}</strong>
                      <p>{plane.purpose}</p>
                      <span>{plane.evidence.join(" / ")}</span>
                    </article>
                  ))}
                </div>
              </section>
            </div>

            <div className="eval-grid">
              {evalRun ? (
                Object.entries(evalRun.metrics)
                  .filter(([, value]) => typeof value !== "object")
                  .map(([key, value]) => (
                    <div key={key} className="eval-metric">
                      <span>{key}</span>
                      <strong>{String(value)}</strong>
                    </div>
                  ))
              ) : (
                <div className="eval-empty">
                  <Gauge size={34} />
                  <strong>暂无评测报告</strong>
                  <p>本地 smoke 与完整云模型评测共用同一套 Harness。</p>
                </div>
              )}
            </div>
            <pre className="report">{evalRun?.markdown_report ?? "Markdown report will appear here."}</pre>
          </section>
        )}

        {activeTab === "system" && (
          <section className="content-band">
            <SectionHead
              icon={<Workflow />}
              title="系统拓扑"
              subtitle="后端健康、工具注册表、LangGraph编排元数据"
              action={
                <IconButton ariaLabel="刷新系统元数据" onClick={() => void refreshSystem()}>
                  {systemBusy ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
                </IconButton>
              }
            />

            <div className="system-grid">
              <section className="work-panel">
                <div className="panel-head compact">
                  <Database />
                  <h2>运行环境</h2>
                </div>
                <div className="health-grid">
                  <OutcomeItem label="API" value={health?.status ?? "offline"} tone={health ? "green" : "red"} />
                  <OutcomeItem label="LLM" value={health?.llm_model ?? "-"} />
                  <OutcomeItem label="PostgreSQL" value={health?.repository_backend ?? "-"} tone={health?.repository_backend === "postgresql" ? "green" : "amber"} />
                  <OutcomeItem label="Redis" value={health?.runtime_backend ?? "-"} tone={health?.runtime_backend === "redis" ? "green" : "amber"} />
                  <OutcomeItem label="Qdrant" value={health?.knowledge_backend ?? "-"} tone={health?.knowledge_backend === "qdrant" ? "green" : "amber"} />
                  <OutcomeItem label="Collection" value={health?.qdrant_collection ?? "-"} />
                </div>
              </section>

              <section className="work-panel">
                <div className="panel-head compact">
                  <GitBranch />
                  <h2>Agent Graph</h2>
                </div>
                <div className="graph-list">
                  {graphNodes.map((node, index) => (
                    <div key={node} className="graph-node">
                      <span>{index + 1}</span>
                      <strong>{node}</strong>
                    </div>
                  ))}
                </div>
                <div className="edge-list">
                  {graphEdges.map((edge, index) => (
                    <span key={`${index}-${formatJson(edge)}`}>{formatEdge(edge)}</span>
                  ))}
                </div>
              </section>

              <section className="work-panel tool-registry">
                <div className="panel-head compact">
                  <Wrench />
                  <h2>MCP-style Tools</h2>
                </div>
                <div className="registry-grid">
                  {tools.map((tool) => {
                    const copy = TOOL_COPY[tool.name];
                    return (
                      <article key={tool.name} className="registry-card">
                        <div>
                          <strong>{copy?.title ?? tool.name}</strong>
                          <span>{tool.name} / {copy?.category ?? tool.category ?? "general"}</span>
                        </div>
                        <p>{copy?.description ?? tool.description ?? "业务工具"}</p>
                      </article>
                    );
                  })}
                </div>
              </section>

              <section className="work-panel">
                <div className="panel-head compact">
                  <Layers3 />
                  <h2>接口闭环</h2>
                </div>
                <div className="interface-list">
                  <InterfaceRow method="POST" path="/api/chat/stream" detail="SSE: agent_step/tool_call/citation/token/final" />
                  <InterfaceRow method="GET" path="/api/conversations/{id}" detail="消息、摘要、trace、工具调用落库快照" />
                  <InterfaceRow method="PATCH" path="/api/tickets/{id}" detail="客服工单状态与优先级回写PostgreSQL" />
                  <InterfaceRow method="POST" path="/api/kb/ingest" detail="在线文档切块并写入Qdrant" />
                  <InterfaceRow method="POST" path="/api/evals/run" detail="Harness质量报告与阈值评估" />
                  <InterfaceRow method="GET" path="/api/harness/manifest" detail="暴露Agent状态契约、工具边界、控制面与发布门禁" />
                </div>
              </section>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}

function buildBusinessOutcome(toolCalls: ToolCall[]) {
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
      detail: String(result?.reason ?? result?.error ?? "退款链路已完成校验。")
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
    title: TOOL_COPY[lastCall.name]?.title ?? lastCall.name,
    status: lastCall.success ? "success" : "failed",
    tone: lastCall.success ? ("green" as const) : ("red" as const),
    detail: String(lastCall.error ?? TOOL_COPY[lastCall.name]?.description ?? "工具调用完成。")
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function formatScore(value?: number) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function formatGateValue(key: string, value: number) {
  if (key.endsWith("_ms")) return `${value}ms`;
  if (key.includes("rate") || key.includes("accuracy")) return `${Math.round(value * 100)}%`;
  return String(value);
}

function formatEdge(edge: unknown) {
  return Array.isArray(edge) ? `${edge[0]} -> ${edge[1]}` : String(edge);
}

function NavButton({
  active,
  icon,
  onClick,
  children
}: {
  active: boolean;
  icon: ReactNode;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button className={active ? "active" : ""} onClick={onClick} type="button">
      {icon}
      <span>{children}</span>
    </button>
  );
}

function StoragePill({ label, value }: { label: string; value: string }) {
  const live = !["offline", "memory", "unknown", "-"].includes(value);
  return (
    <div className="storage-pill">
      <span>{label}</span>
      <strong className={live ? "live" : ""}>{value}</strong>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  detail,
  tone
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone: "green" | "blue" | "amber" | "red";
}) {
  return (
    <article className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <p>{detail}</p>
      </div>
    </article>
  );
}

function IconButton({
  children,
  ariaLabel,
  onClick
}: {
  children: ReactNode;
  ariaLabel: string;
  onClick: () => void;
}) {
  return (
    <button className="icon-button" type="button" aria-label={ariaLabel} onClick={onClick}>
      {children}
    </button>
  );
}

function StatusChip({
  icon,
  label,
  tone = "neutral"
}: {
  icon?: ReactNode;
  label: string;
  tone?: "neutral" | "green" | "red" | "amber" | "blue";
}) {
  return (
    <span className={`status-chip ${tone}`}>
      {icon}
      {label}
    </span>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head">
        {icon}
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function SectionHead({
  icon,
  title,
  subtitle,
  action
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  action: ReactNode;
}) {
  return (
    <div className="section-head">
      <div className="section-title">
        <span>{icon}</span>
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      {action}
    </div>
  );
}

function OutcomeItem({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "neutral" | "green" | "amber" | "red" | "blue";
}) {
  return (
    <div className={`outcome-item ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InterfaceRow({ method, path, detail }: { method: string; path: string; detail: string }) {
  return (
    <div className="interface-row">
      <span>{method}</span>
      <strong>{path}</strong>
      <p>{detail}</p>
      <ArrowUpRight size={16} />
    </div>
  );
}

function EmptyInline({ text }: { text: string }) {
  return (
    <div className="empty-inline">
      <AlertTriangle size={16} />
      <span>{text}</span>
    </div>
  );
}
