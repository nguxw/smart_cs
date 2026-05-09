import type { ReactNode } from "react";

export function Button({
  children,
  onClick,
  disabled,
  tone = "primary",
  type = "button",
  ariaLabel
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "primary" | "subtle" | "danger";
  type?: "button" | "submit";
  ariaLabel?: string;
}) {
  return (
    <button
      className={tone === "primary" ? "primary-action" : `subtle-action ${tone}`}
      type={type}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
