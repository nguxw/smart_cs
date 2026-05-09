import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "neutral",
  icon
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "red" | "amber" | "blue";
  icon?: ReactNode;
}) {
  return (
    <span className={`status-chip ${tone}`}>
      {icon}
      {children}
    </span>
  );
}
