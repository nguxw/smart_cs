import { AlertTriangle } from "lucide-react";

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty-inline">
      <AlertTriangle size={16} />
      <span>{text}</span>
    </div>
  );
}
