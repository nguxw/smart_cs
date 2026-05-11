import { BrainCircuit, CheckCircle2, Database, Inbox, ShieldCheck, XCircle } from "lucide-react";
import type { FormEvent } from "react";
import { useCallback, useMemo, useState } from "react";

import { PageShell } from "./app/layout/PageShell";
import { Sidebar } from "./app/layout/Sidebar";
import { Topbar } from "./app/layout/Topbar";
import { useCases } from "./hooks/useCases";
import { useChatStream } from "./hooks/useChatStream";
import { useEvalRun } from "./hooks/useEvalRun";
import { useKnowledgeSearch } from "./hooks/useKnowledgeSearch";
import { useSystemHealth } from "./hooks/useSystemHealth";
import { useTickets } from "./hooks/useTickets";
import { CasesPage } from "./pages/cases/CasesPage";
import { DeskPage } from "./pages/desk/DeskPage";
import { EvalPage } from "./pages/evals/EvalPage";
import { KnowledgePage } from "./pages/knowledge/KnowledgePage";
import { SystemPage } from "./pages/system/SystemPage";
import { TicketsPage } from "./pages/tickets/TicketsPage";
import type { TabKey, Ticket } from "./types/api";

const TAB_KEYS: TabKey[] = ["desk", "cases", "tickets", "kb", "evals", "system"];

function readInitialTab(): TabKey {
  const tab = new URLSearchParams(window.location.search).get("tab") as TabKey | null;
  return tab && TAB_KEYS.includes(tab) ? tab : "desk";
}

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>(() => readInitialTab());
  const [userId, setUserId] = useState("u_1001");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const system = useSystemHealth();
  const tickets = useTickets();
  const cases = useCases();
  const ticketThreadConversation = tickets.thread?.conversation;
  const refreshTicketThread = tickets.refreshThread;
  const refreshOperations = useCallback(async () => {
    await Promise.all([tickets.refresh(), cases.refresh()]);
  }, [cases.refresh, tickets.refresh]);
  const navigateToTab = useCallback((nextTab: TabKey) => {
    setActiveTab(nextTab);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", nextTab);
    window.history.replaceState({}, "", url);
  }, []);
  const saveTicketAndRefreshCases = useCallback(
    async (ticketId: string, payload: Partial<Ticket>) => {
      const updated = await tickets.saveTicket(ticketId, payload);
      await cases.refresh();
      return updated;
    },
    [cases.refresh, tickets.saveTicket]
  );
  const chat = useChatStream(userId, refreshOperations);
  const openTicketConversation = useCallback(
    async (conversationId: string, nextUserId: string) => {
      setUserId(nextUserId);
      await chat.loadConversation(conversationId);
      navigateToTab("desk");
    },
    [chat.loadConversation, navigateToTab]
  );
  const handleNavigate = useCallback(
    (nextTab: TabKey) => {
      if (nextTab === "desk" && activeTab === "tickets") {
        void (async () => {
          try {
            const ticketConversation =
              ticketThreadConversation ?? (await refreshTicketThread())?.conversation;
            if (ticketConversation) {
              await openTicketConversation(ticketConversation.id, ticketConversation.user_id);
              return;
            }
          } catch (cause) {
            console.warn("Failed to open linked ticket conversation", cause);
          }
          navigateToTab(nextTab);
        })();
        return;
      }
      navigateToTab(nextTab);
    },
    [activeTab, navigateToTab, openTicketConversation, refreshTicketThread, ticketThreadConversation]
  );
  const knowledge = useKnowledgeSearch();
  const evals = useEvalRun();

  const storageReady =
    system.health?.repository_backend === "postgresql" &&
    system.health?.runtime_backend === "redis" &&
    system.health?.knowledge_backend === "qdrant";

  const refreshAll = useCallback(async () => {
    setNotice(null);
    setError(null);
    try {
      await Promise.all([system.refresh(), tickets.refresh(), cases.refresh(), knowledge.search()]);
      setNotice("控制台数据已刷新");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "刷新失败");
    }
  }, [cases.refresh, knowledge, system, tickets]);

  const ticketStats = tickets.stats;
  const caseStats = cases.stats;
  const activeError = error ?? chat.error ?? cases.error;

  const metrics = useMemo(
    () => [
      {
        icon: <Database />,
        label: "数据底座",
        value: storageReady ? "生产形态" : system.health ? "降级模式" : "离线",
        tone: storageReady ? "green" : "amber",
        detail: `${system.health?.repository_backend ?? "-"} / ${system.health?.runtime_backend ?? "-"} / ${system.health?.knowledge_backend ?? "-"}`
      },
      {
        icon: <BrainCircuit />,
        label: "运行路径",
        value: `${chat.agentSteps.length} 节点`,
        tone: "blue",
        detail: `Orchestrator sequence，累计 ${chat.agentLatency}ms`
      },
      {
        icon: <Inbox />,
        label: "服务案件",
        value: `${caseStats.active} 活跃`,
        tone: caseStats.high > 0 ? "red" : caseStats.waiting > 0 ? "amber" : "green",
        detail: `${caseStats.waiting} 待客户确认 / ${caseStats.handoff} 人工接管`
      },
      {
        icon: <ShieldCheck />,
        label: "合规状态",
        value: chat.pendingConfirmation ? "待确认" : "正常",
        tone: chat.pendingConfirmation ? "amber" : "green",
        detail: `${ticketStats.open} 工单待处理 / ${ticketStats.high} 高优先级`
      }
    ],
    [
      chat.agentLatency,
      chat.agentSteps.length,
      chat.pendingConfirmation,
      caseStats.active,
      caseStats.handoff,
      caseStats.high,
      caseStats.waiting,
      storageReady,
      system.health,
      ticketStats.high,
      ticketStats.open,
      ticketStats.resolved
    ]
  );

  function handleUserChange(nextUserId: string) {
    setUserId(nextUserId);
    chat.reset();
  }

  async function runEval() {
    try {
      const body = await evals.run();
      setNotice(`评测完成：${body.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "评测运行失败");
    }
  }

  async function ingestKnowledge(event: FormEvent) {
    try {
      const count = await knowledge.ingest(event);
      setNotice(`知识库已写入 ${count ?? 0} 个 chunk`);
      return count;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "知识库导入失败");
      return undefined;
    }
  }

  return (
    <div className="app-shell">
      <Sidebar activeTab={activeTab} onNavigate={handleNavigate} health={system.health} />
      <PageShell>
        <Topbar
          userId={userId}
          onUserChange={handleUserChange}
          health={system.health}
          latestIntent={chat.latestIntent}
          conversationId={chat.conversationId}
          onRefresh={() => void refreshAll()}
        />

        {(notice || activeError) && (
          <div className={`notice ${activeError ? "error" : ""}`} role="status">
            {activeError ? <XCircle size={17} /> : <CheckCircle2 size={17} />}
            <span>{activeError ?? notice}</span>
          </div>
        )}

        <section className="metric-grid" aria-label="核心运行指标">
          {metrics.map((metric) => (
            <article key={metric.label} className={`metric ${metric.tone}`}>
              <div className="metric-icon">{metric.icon}</div>
              <div>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <p>{metric.detail}</p>
              </div>
            </article>
          ))}
        </section>

        {activeTab === "desk" && (
          <DeskPage
            userId={userId}
            onScenarioUser={handleUserChange}
            chat={chat}
          />
        )}

        {activeTab === "cases" && (
          <CasesPage
            cases={cases.cases}
            selectedCase={cases.selectedCase}
            detail={cases.detail}
            onSelectCase={(caseId) => void cases.selectCase(caseId)}
            onRefresh={() => void cases.refresh()}
            busy={cases.busy}
          />
        )}

        {activeTab === "tickets" && (
          <TicketsPage
            tickets={tickets.tickets}
            selectedTicket={tickets.selectedTicket}
            thread={tickets.thread}
            threadBusy={tickets.threadBusy}
            onSelectTicket={tickets.setSelectedTicketId}
            onSaveTicket={saveTicketAndRefreshCases}
            onRefreshThread={() => void tickets.refreshThread()}
            onOpenConversation={(conversationId, conversationUserId) =>
              void openTicketConversation(conversationId, conversationUserId)
            }
            onRefresh={() => void refreshOperations()}
            busy={tickets.busy}
          />
        )}

        {activeTab === "kb" && (
          <KnowledgePage
            query={knowledge.query}
            setQuery={knowledge.setQuery}
            category={knowledge.category}
            setCategory={knowledge.setCategory}
            results={knowledge.results}
            busy={knowledge.busy}
            form={knowledge.form}
            setForm={knowledge.setForm}
            onSearch={knowledge.search}
            onIngest={ingestKnowledge}
          />
        )}

        {activeTab === "evals" && (
          <EvalPage
            harness={system.harness}
            evalRun={evals.evalRun}
            evalSize={evals.evalSize}
            setEvalSize={evals.setEvalSize}
            busy={evals.busy}
            onRun={runEval}
          />
        )}

        {activeTab === "system" && (
          <SystemPage
            health={system.health}
            graph={system.graph}
            harness={system.harness}
            tools={system.tools}
            busy={system.busy}
            onRefresh={() => void system.refresh()}
          />
        )}
      </PageShell>
    </div>
  );
}
