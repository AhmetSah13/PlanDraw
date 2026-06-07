import { cn } from "../lib/cn";

type PillVariant = "cyan" | "emerald" | "amber" | "red" | "slate" | "violet";

interface StatusPillProps {
  label: string;
  variant?: PillVariant;
  pulse?: boolean;
}

const variants: Record<PillVariant, string> = {
  cyan: "border-cyan-500/40 bg-cyan-500/10 text-cyan-200",
  emerald: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  amber: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  red: "border-red-500/50 bg-red-500/15 text-red-200",
  slate: "border-slate-600/50 bg-slate-800/50 text-slate-300",
  violet: "border-violet-500/40 bg-violet-500/10 text-violet-200",
};

export function StatusPill({ label, variant = "slate", pulse }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-wide",
        variants[variant],
        pulse && "animate-pulse",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          variant === "emerald" && "bg-emerald-400 shadow-[0_0_6px_#34d399]",
          variant === "cyan" && "bg-cyan-400 shadow-[0_0_6px_#22d3ee]",
          variant === "red" && "bg-red-400 shadow-[0_0_6px_#f87171]",
          variant === "amber" && "bg-amber-400",
          variant === "violet" && "bg-violet-400",
          variant === "slate" && "bg-slate-500",
        )}
      />
      {label}
    </span>
  );
}
