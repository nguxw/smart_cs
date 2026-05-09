import type { ReactNode } from "react";

export function Card({
  title,
  icon,
  children,
  className = ""
}: {
  title?: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          {icon}
          <h2>{title}</h2>
        </div>
      )}
      {children}
    </section>
  );
}
