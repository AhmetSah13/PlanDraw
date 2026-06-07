import { motion } from "framer-motion";
import { Check, Circle, Loader2, X } from "lucide-react";
import type { StepStatus } from "../content/tr";
import { tr } from "../content/tr";
import { cn } from "../lib/cn";

export type PipelineStepId = "upload" | "analyze" | "compile" | "simulate" | "send";

const steps: { id: PipelineStepId; label: string }[] = [
  { id: "upload", label: tr.pipeline.upload },
  { id: "analyze", label: tr.pipeline.analyze },
  { id: "compile", label: tr.pipeline.compile },
  { id: "simulate", label: tr.pipeline.simulate },
  { id: "send", label: tr.pipeline.send },
];

const statusText: Record<StepStatus, string> = {
  waiting: tr.pipeline.status.waiting,
  ready: tr.pipeline.status.ready,
  success: tr.pipeline.status.success,
  error: tr.pipeline.status.error,
};

interface PipelineStepperProps {
  statuses: Record<PipelineStepId, StepStatus>;
  busy?: boolean;
}

function StepIcon({ status, busy }: { status: StepStatus; busy?: boolean }) {
  if (busy && status === "ready") {
    return <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />;
  }
  if (status === "success") {
    return <Check className="h-4 w-4 text-emerald-400" />;
  }
  if (status === "error") {
    return <X className="h-4 w-4 text-red-400" />;
  }
  if (status === "ready") {
    return <Circle className="h-4 w-4 fill-cyan-500/30 text-cyan-400" />;
  }
  return <Circle className="h-4 w-4 text-slate-600" />;
}

export function PipelineStepper({ statuses, busy }: PipelineStepperProps) {
  return (
    <div className="glass-panel glow-border overflow-hidden">
      <div className="border-b border-white/5 px-5 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400/90">
          {tr.pipeline.title}
        </h2>
      </div>
      <div className="flex flex-col gap-0 p-4 lg:flex-row lg:items-stretch lg:gap-2">
        {steps.map((step, index) => {
          const status = statuses[step.id];
          const isLast = index === steps.length - 1;
          return (
            <div key={step.id} className="flex flex-1 items-center lg:flex-col lg:items-stretch">
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className={cn(
                  "relative flex flex-1 flex-col rounded-xl border px-4 py-3 transition-colors",
                  status === "success" && "border-emerald-500/30 bg-emerald-500/5",
                  status === "error" && "border-red-500/30 bg-red-500/5",
                  status === "ready" && "border-cyan-500/35 bg-cyan-500/5 shadow-glow-sm",
                  status === "waiting" && "border-white/5 bg-slate-900/30",
                )}
              >
                <div className="flex items-center gap-2">
                  <StepIcon status={status} busy={busy && status === "ready"} />
                  <span className="text-sm font-semibold text-slate-100">{step.label}</span>
                </div>
                <span
                  className={cn(
                    "mt-1 text-[10px] uppercase tracking-wider",
                    status === "success" && "text-emerald-400/90",
                    status === "error" && "text-red-400/90",
                    status === "ready" && "text-cyan-400/90",
                    status === "waiting" && "text-slate-600",
                  )}
                >
                  {statusText[status]}
                </span>
                {status === "success" ? (
                  <motion.div
                    layoutId={`pipe-glow-${step.id}`}
                    className="pointer-events-none absolute inset-0 rounded-xl ring-1 ring-emerald-400/20"
                  />
                ) : null}
              </motion.div>
              {!isLast ? (
                <div className="mx-2 hidden h-px flex-1 bg-gradient-to-r from-cyan-500/20 via-violet-500/20 to-transparent lg:mx-0 lg:mt-2 lg:h-8 lg:w-px lg:flex-none lg:bg-gradient-to-b" />
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
