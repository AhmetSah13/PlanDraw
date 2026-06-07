import type { ReactNode } from "react";
import { cn } from "../lib/cn";

interface GlowCardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  accent?: boolean;
}

export function GlowCard({ title, subtitle, children, className, accent }: GlowCardProps) {
  return (
    <section
      className={cn(
        "glass-panel glow-border overflow-hidden",
        accent && "border-cyan-500/25 shadow-glow",
        className,
      )}
    >
      {(title || subtitle) && (
        <header className="border-b border-white/5 px-5 py-3.5">
          {title ? (
            <h2 className="text-sm font-semibold tracking-wide text-slate-100">{title}</h2>
          ) : null}
          {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}
