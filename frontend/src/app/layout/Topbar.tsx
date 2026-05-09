import { RefreshCw } from "lucide-react";

import type { Health } from "../../types/api";
import { USERS } from "../../shared/demoData";

export function Topbar({
  userId,
  onUserChange,
  health,
  latestIntent,
  conversationId,
  onRefresh
}: {
  userId: string;
  onUserChange: (userId: string) => void;
  health: Health | null;
  latestIntent: string;
  conversationId: string | null;
  onRefresh: () => void;
}) {
  return (
    <header className="topbar">
      <div className="title-block">
        <p className="eyebrow">Agentic Customer Support</p>
        <h1>Case-driven 智能客服运营平台</h1>
        <span>
          业务意图 <b>{latestIntent}</b>
          <span className="dot-separator" />
          {conversationId ? `会话 ${conversationId.slice(0, 8)}` : "新会话"}
          <span className="dot-separator" />
          {health ? `${health.llm_provider} / ${health.llm_model}` : "API offline"}
        </span>
      </div>

      <div className="top-actions">
        <label className="user-select">
          <span>开发态 AuthContext</span>
          <select value={userId} onChange={(event) => onUserChange(event.target.value)}>
            {USERS.map((user) => (
              <option key={user.id} value={user.id}>
                {user.id} / {user.name} / {user.tier}
              </option>
            ))}
          </select>
        </label>
        <button className="icon-button" type="button" aria-label="刷新后端状态" onClick={onRefresh}>
          <RefreshCw size={18} />
        </button>
      </div>
    </header>
  );
}
