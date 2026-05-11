import { FormEvent, useState } from "react";
import { Bot, CheckCircle2, Loader2, Send } from "lucide-react";

import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import type { ChatMessage } from "../../types/api";
import { SCENARIOS } from "../../shared/demoData";

export function ChatPanel({
  userId,
  busy,
  messages,
  onSend,
  onScenario,
  onReset
}: {
  userId: string;
  busy: boolean;
  messages: ChatMessage[];
  onSend: (message: string) => Promise<void>;
  onScenario: (userId: string, prompt: string) => void;
  onReset: () => void;
}) {
  const [input, setInput] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message) return;
    setInput("");
    await onSend(message);
  }

  return (
    <section className="chat-pane agent-console" aria-label="客服会话处理台">
      <div className="pane-head">
        <div>
          <h2>会话处理</h2>
          <p>先判断客户意图，再把任务、证据和副作用动作挂到同一个服务案件。</p>
        </div>
        <div className="head-actions">
          <Button
            tone="subtle"
            onClick={() => {
              setInput("");
              onReset();
            }}
          >
            新会话
          </Button>
          {busy ? (
            <Badge icon={<Loader2 className="spin" />} tone="blue">
              流式响应
            </Badge>
          ) : (
            <Badge icon={<CheckCircle2 />} tone="green">
              就绪
            </Badge>
          )}
        </div>
      </div>

      <div className="scenario-grid compact" aria-label="售后场景">
        {SCENARIOS.map((scenario) => (
          <button
            key={scenario.label}
            type="button"
            className={scenario.userId === userId && scenario.prompt === input ? "scenario active" : "scenario"}
            onClick={() => {
              setInput(scenario.prompt);
              onScenario(scenario.userId, scenario.prompt);
            }}
          >
            <span>{scenario.label}</span>
            <strong>{scenario.intent}</strong>
            <em>风险 {scenario.risk}</em>
          </button>
        ))}
      </div>

      <div className="messages dense" aria-live="polite">
        {messages.length === 0 && (
          <div className="empty-state">
            <Bot size={34} />
            <strong>等待客户问题</strong>
            <p>系统会创建服务案件、判断任务、生成推荐动作，并保留工具审计。</p>
          </div>
        )}
        {messages.map((message, index) => (
          <article key={`${message.role}-${index}`} className={`bubble ${message.role}`}>
            <span>{message.role === "assistant" ? "Agent" : "Customer"}</span>
            <p>{message.content || (busy ? "正在接收流式回复..." : "")}</p>
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
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
  );
}
