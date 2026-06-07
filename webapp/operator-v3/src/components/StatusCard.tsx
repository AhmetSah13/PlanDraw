type StatusVariant = "success" | "warning" | "error" | "neutral" | "info";

interface StatusCardProps {
  title: string;
  value: string;
  detail?: string;
  variant?: StatusVariant;
}

const variantStyles: Record<StatusVariant, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  error: "border-red-200 bg-red-50 text-red-900",
  neutral: "border-slate-200 bg-white text-slate-800",
  info: "border-sky-200 bg-sky-50 text-sky-900",
};

export function StatusCard({ title, value, detail, variant = "neutral" }: StatusCardProps) {
  return (
    <div className={`rounded-2xl border p-4 shadow-card ${variantStyles[variant]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{title}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
      {detail ? <p className="mt-1 text-xs opacity-80">{detail}</p> : null}
    </div>
  );
}
