import type { ReactNode } from "react";

export function SplitPane({
  left,
  center,
  right
}: {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}) {
  return (
    <section className="support-desk-grid">
      <aside className="context-rail">{left}</aside>
      <section className="conversation-column">{center}</section>
      <aside className="action-rail">{right}</aside>
    </section>
  );
}
