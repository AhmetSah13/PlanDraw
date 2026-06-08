import type { PipelineStepId } from "../components/PipelineStepper";
import type { MissionSection, StepStatus } from "../content/tr";
import type { AnalyzeResponse } from "../types/api";

export type CompileSource = "demo" | "manual";

export interface WorkflowGateInput {
  backendOnline: boolean;
  busy: boolean;
  hasSelectedFile: boolean;
  hasCommands: boolean;
  compileStatus: StepStatus;
  simulationStatus: StepStatus;
  dryRunPassed: boolean;
  preflight: AnalyzeResponse | null;
  penSafeKnown: boolean;
  penSafe: boolean;
}

export interface WorkflowAvailability {
  canCompile: boolean;
  canDryRun: boolean;
  canSimulate: boolean;
  canLive: boolean;
  compileReason: string | null;
  dryRunReason: string | null;
  simulateReason: string | null;
  liveReason: string | null;
}

export const SECTION_IDS: Record<MissionSection, string> = {
  sistem: "section-sistem",
  plan: "section-plan",
  derleme: "section-derleme",
  simulasyon: "section-simulasyon",
  robot: "section-robot",
  loglar: "section-loglar",
};

export const SECTION_ORDER: MissionSection[] = [
  "sistem",
  "plan",
  "derleme",
  "simulasyon",
  "robot",
  "loglar",
];

export const SECTION_PURPOSE: Record<MissionSection, string> = {
  sistem: "Sistem durumu ve görev akışı",
  plan: "Hazır demo planları ve plan seçimi",
  derleme: "Plan derleme ve komut üretimi",
  simulasyon: "CAD önizleme ve simülasyon geri bildirimi",
  robot: "Dry-run, canlı gönderim ve durdurma kontrolleri",
  loglar: "Komut akışı ve olay günlüğü",
};

export function getPostCompileNavigation(source: CompileSource): MissionSection | null {
  return source === "manual" ? "derleme" : null;
}

function reason(value: boolean, message: string): string | null {
  return value ? message : null;
}

function firstReason(...items: Array<string | null>): string | null {
  return items.find((item) => item !== null) ?? null;
}

export function buildWorkflowAvailability(input: WorkflowGateInput): WorkflowAvailability {
  const compileReason = firstReason(
    reason(input.busy, "İşlem sürüyor."),
    reason(!input.backendOnline, "Backend bağlantısı yok."),
    reason(!input.hasSelectedFile, "Önce DXF veya JSON plan seçin."),
  );

  const dryRunReason = firstReason(
    reason(input.busy, "İşlem sürüyor."),
    reason(!input.backendOnline, "Backend bağlantısı yok."),
    reason(!input.hasCommands, "Önce planı derleyin."),
    reason(input.compileStatus !== "success", "Plan başarıyla derlenmeden dry-run yapılamaz."),
    reason(input.penSafeKnown && !input.penSafe, "Pen-safe derleme temiz değil."),
    reason(input.preflight?.blocked === true, "Analiz sonucu engelli; dry-run başlatılamaz."),
  );

  const simulateReason = firstReason(
    reason(input.busy, "İşlem sürüyor."),
    reason(!input.hasCommands, "Önce planı derleyin."),
    reason(!input.dryRunPassed, "Önce Komutları Test Et (Dry-run) adımını başarıyla tamamlayın."),
  );

  const liveReason = firstReason(
    reason(input.busy, "İşlem sürüyor."),
    reason(!input.backendOnline, "Backend bağlantısı yok."),
    reason(!input.hasCommands, "Önce planı derleyin."),
    reason(!input.dryRunPassed, "Canlı gönderimden önce dry-run başarıyla tamamlanmalı."),
    reason(input.simulationStatus !== "success", "Canlı gönderimden önce simülasyon başarıyla tamamlanmalı."),
    reason(!input.preflight, "Canlı gönderimden önce analiz sonucu gerekli."),
    reason(input.preflight?.blocked === true, "Analiz sonucu engelli; canlı gönderim kapalı."),
    reason(input.penSafeKnown && !input.penSafe, "Pen-safe derleme temiz değil."),
  );

  return {
    canCompile: compileReason === null,
    canDryRun: dryRunReason === null,
    canSimulate: simulateReason === null,
    canLive: liveReason === null,
    compileReason,
    dryRunReason,
    simulateReason,
    liveReason,
  };
}

export function resetDerivedPipelineForAction(
  pipeline: Record<PipelineStepId, StepStatus>,
  action: "dryRun" | "simulate" | "live",
): Record<PipelineStepId, StepStatus> {
  if (action === "dryRun") {
    return { ...pipeline, simulate: "waiting", send: "waiting" };
  }
  if (action === "simulate") {
    return { ...pipeline, send: "waiting" };
  }
  return pipeline;
}
