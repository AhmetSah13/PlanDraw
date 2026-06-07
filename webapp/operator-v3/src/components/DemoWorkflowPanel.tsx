import { ArrowRight, FlaskConical, Layers, Radio, Upload } from "lucide-react";
import type { PipelineStepId } from "./PipelineStepper";
import type { StepStatus } from "../content/tr";
import { tr } from "../content/tr";
import { DEMO_PLANS, type DemoPlanId } from "../services/demoPlans";
import { cn } from "../lib/cn";

const flowSteps: {
  id: string;
  label: string;
  icon: typeof Upload;
  pipelineKeys: PipelineStepId[];
}[] = [
  { id: "upload", label: tr.demo.steps.upload, icon: Upload, pipelineKeys: ["upload"] },
  {
    id: "compile",
    label: tr.demo.steps.compile,
    icon: Layers,
    pipelineKeys: ["analyze", "compile"],
  },
  { id: "stream", label: tr.demo.steps.stream, icon: FlaskConical, pipelineKeys: [] },
  {
    id: "run",
    label: tr.demo.steps.run,
    icon: Radio,
    pipelineKeys: ["simulate", "send"],
  },
];

function stepTone(
  keys: PipelineStepId[],
  pipeline: Record<PipelineStepId, StepStatus>,
  hasCommands: boolean,
  stepId: string,
): "active" | "done" | "idle" {
  if (stepId === "stream") {
    if (hasCommands) return "done";
    if (pipeline.compile === "ready") return "active";
    return "idle";
  }
  if (!keys.length) return "idle";
  if (keys.some((k) => pipeline[k] === "error")) return "active";
  if (keys.every((k) => pipeline[k] === "success")) return "done";
  if (keys.some((k) => pipeline[k] === "ready" || pipeline[k] === "success")) return "active";
  return "idle";
}

interface DemoWorkflowPanelProps {
  pipeline: Record<PipelineStepId, StepStatus>;
  hasCommands: boolean;
  backendOnline: boolean;
  busy: boolean;
  onDemoSelect: (id: DemoPlanId) => void;
}

export function DemoWorkflowPanel({
  pipeline,
  hasCommands,
  backendOnline,
  busy,
  onDemoSelect,
}: DemoWorkflowPanelProps) {
  return (
    <div className="glass-panel glow-border overflow-hidden">
      <div className="border-b border-white/5 px-5 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400/90">
          {tr.demo.title}
        </h2>
        <p className="mt-1 text-[11px] text-slate-500">{tr.demo.hint}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-5 py-4">
        {flowSteps.map((step, index) => {
          const tone = stepTone(step.pipelineKeys, pipeline, hasCommands, step.id);
          const Icon = step.icon;
          return (
            <div key={step.id} className="flex items-center gap-2">
              <div
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors",
                  tone === "done" && "border-emerald-500/35 bg-emerald-500/10 text-emerald-200",
                  tone === "active" && "border-cyan-500/40 bg-cyan-500/10 text-cyan-100 shadow-glow-sm",
                  tone === "idle" && "border-white/5 bg-slate-900/40 text-slate-500",
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0 opacity-80" />
                {step.label}
              </div>
              {index < flowSteps.length - 1 ? (
                <ArrowRight className="hidden h-3.5 w-3.5 text-slate-700 sm:block" />
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="border-t border-white/5 px-5 py-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          {tr.demo.samplesTitle}
        </p>
        <p className="mt-1 text-[11px] text-slate-600">{tr.demo.samplesHint}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {DEMO_PLANS.map((plan) => (
            <button
              key={plan.id}
              type="button"
              className="btn-ghost flex-col items-start gap-1 py-3 text-left"
              disabled={!backendOnline || busy}
              onClick={() => onDemoSelect(plan.id)}
            >
              <span className="text-sm font-semibold text-slate-200">{plan.label}</span>
              <span className="text-[10px] leading-snug text-slate-500">{plan.description}</span>
            </button>
          ))}
        </div>
        {!backendOnline ? (
          <p className="mt-3 text-[11px] text-amber-400/80">{tr.errors.backendOffline}</p>
        ) : null}
      </div>
    </div>
  );
}
