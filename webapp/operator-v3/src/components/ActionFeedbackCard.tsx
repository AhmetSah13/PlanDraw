import { AlertCircle, CheckCircle2, Loader2, Radio, Play, Send } from "lucide-react";
import type { ActionFeedback } from "../lib/workflowState";
import { cn } from "../lib/cn";

const kindIcon = {
  dryRun: Play,
  simulate: Radio,
  live: Send,
} as const;

interface ActionFeedbackCardProps {
  feedback: ActionFeedback | null;
}

export function ActionFeedbackCard({ feedback }: ActionFeedbackCardProps) {
  if (!feedback || feedback.phase === "idle") return null;

  const Icon = kindIcon[feedback.kind];
  const isRunning = feedback.phase === "running";
  const isSuccess = feedback.phase === "success";
  const isError = feedback.phase === "error";

  return (
    <div
      className={cn(
        "mt-4 rounded-xl border px-4 py-3",
        isRunning && "border-cyan-500/35 bg-cyan-500/5",
        isSuccess && "border-emerald-500/35 bg-emerald-500/5",
        isError && "border-red-500/35 bg-red-500/5",
      )}
    >
      <div className="flex items-start gap-3">
        {isRunning ? (
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-cyan-400" />
        ) : isSuccess ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
        ) : (
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Icon className="h-3.5 w-3.5 text-slate-500" />
            <p className="text-sm font-semibold text-slate-100">{feedback.title}</p>
          </div>
          <p
            className={cn(
              "mt-1 text-xs leading-relaxed",
              isError ? "text-red-300/90" : isSuccess ? "text-emerald-200/90" : "text-cyan-200/80",
            )}
          >
            {feedback.message}
          </p>
          {feedback.detail ? (
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{feedback.detail}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
