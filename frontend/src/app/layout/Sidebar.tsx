import { Sparkles } from "lucide-react";

import { NAV_ITEMS } from "../router";
import type { Health, TabKey } from "../../types/api";

export function Sidebar({
  activeTab,
  onNavigate,
  health
}: {
  activeTab: TabKey;
  onNavigate: (tab: TabKey) => void;
  health: Health | null;
}) {
  return (
    <aside className="sidebar" aria-label="主导航">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <Sparkles size={20} />
        </div>
        <div>
          <strong>SmartCS</strong>
          <span>CaseOps</span>
        </div>
      </div>

      <nav className="nav-list">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            className={activeTab === item.key ? "active" : ""}
            type="button"
            onClick={() => onNavigate(item.key)}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="storage-stack" aria-label="数据底座状态">
        <StoragePill label="PostgreSQL" value={health?.repository_backend ?? "offline"} />
        <StoragePill label="Redis" value={health?.runtime_backend ?? "offline"} />
        <StoragePill label="Qdrant" value={health?.knowledge_backend ?? "offline"} />
      </div>
    </aside>
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
