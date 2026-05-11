import type { UseChatStreamReturn } from "./types";
import { SplitPane } from "../../components/SplitPane";
import { ChatPanel } from "./ChatPanel";
import { CustomerProfile } from "./CustomerProfile";
import { ActionPanel } from "./ActionPanel";
import { ActionPlanPanel } from "./ActionPlanPanel";
import { AgentTimeline } from "./AgentTimeline";
import { ToolTracePanel } from "./ToolTracePanel";
import { CitationPanel } from "./CitationPanel";

export function DeskPage({
  userId,
  onScenarioUser,
  chat
}: {
  userId: string;
  onScenarioUser: (userId: string) => void;
  chat: UseChatStreamReturn;
}) {
  return (
    <SplitPane
      left={
        <CustomerProfile
          userId={userId}
          supportCase={chat.currentCase}
          task={chat.currentTask}
        />
      }
      center={
        <ChatPanel
          userId={userId}
          busy={chat.busy}
          messages={chat.messages}
          onSend={chat.send}
          onScenario={(scenarioUserId) => onScenarioUser(scenarioUserId)}
          onReset={chat.reset}
        />
      }
      right={
        <div className="inspector-stack">
          <ActionPlanPanel plan={chat.actionPlan} />
          <ActionPanel
            toolCalls={chat.toolCalls}
            task={chat.currentTask}
            pendingConfirmation={chat.pendingConfirmation}
            busy={chat.busy}
            onApprove={chat.approveTask}
          />
          <CitationPanel citations={chat.citations} />
          <ToolTracePanel toolCalls={chat.toolCalls} />
          <AgentTimeline steps={chat.agentSteps} />
        </div>
      }
    />
  );
}
