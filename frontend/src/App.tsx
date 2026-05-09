import { BrainCircuit, CheckCircle2, Database, Inbox, ShieldCheck, XCircle } from "lucide-react";
import type { FormEvent } from "react";
import { useCallback, useMemo, useState } from "react";

import { PageShell } from "./app/layout/PageShell";
import { Sidebar } from "./app/layout/Sidebar";
import { Topbar } from "./app/layout/Topbar";
import { useChatStream } from "./hooks/useChatStream";
import { useEvalRun } from "./hooks/useEvalRun";
import { useKnowledgeSearch } from "./hooks/useKnowledgeSearch";
import { useSystemHealth } from "./hooks/useSystemHealth";
import { useTickets } from "./hooks/useTickets";
import { DeskPage } from "./pages/desk/DeskPage";
import { EvalPage } from "./pages/evals/EvalPage";
import { KnowledgePage } from "./pages/knowledge/KnowledgePage";
import { SystemPage } from "./pages/system/SystemPage";
import { TicketsPage } from "./pages/tickets/TicketsPage";
import type { TabKey } from "./types/api";

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("desk");
  const [userId, setUserId] = useState("u_1001");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const system = useSystemHealth();
  const tickets = useTickets();
  const chat = useChatStream(userId, tickets.refresh);
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
      await Promise.all([system.refresh(), tickets.refresh(), knowledge.search()]);
      setNotice("控制台数据已刷新");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "刷新失败");
    }
  }, [knowledge, system, tickets]);

  const ticketStats = tickets.stats;
  const activeError = error ?? chat.error;

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
        label: "Agent 状态图",
        value: `${chat.agentSteps.length} 节点`,
        tone: "blue",
        detail: `累计 ${chat.agentLatency}ms，Guardrail ${chat.latestGuardrail}`
      },
      {
        icon: <Inbox />,
        label: "坐席队列",
        value: `${ticketStats.open} 待处理`,
        tone: ticketStats.high > 0 ? "red" : "amber",
        detail: `${ticketStats.high} 高优先级 / ${ticketStats.resolved} 已解决`
      },
      {
        icon: <ShieldCheck />,
        label: "合规状态",
        value: chat.pendingConfirmation ? "待确认" : "正常",
        tone: chat.pendingConfirmation ? "amber" : "green",
        detail: "AuthContext、ToolPolicy、幂等和审计已接入"
      }
    ],
    [
      chat.agentLatency,
      chat.agentSteps.length,
      chat.latestGuardrail,
      chat.pendingConfirmation,
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
      <Sidebar activeTab={activeTab} onNavigate={setActiveTab} health={system.health} />
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

        {activeTab === "tickets" && (
          <TicketsPage
            tickets={tickets.tickets}
            selectedTicket={tickets.selectedTicket}
            onSelectTicket={tickets.setSelectedTicketId}
            onSaveTicket={tickets.saveTicket}
            onRefresh={() => void tickets.refresh()}
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
