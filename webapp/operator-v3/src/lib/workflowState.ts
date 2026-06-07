import type { PipelineStepId } from "../components/PipelineStepper";
import type { StepStatus } from "../content/tr";
import type { ExecuteSerialResponse } from "../types/api";

export type LogLevel = "INFO" | "OK" | "SIM" | "DRY" | "ERR";

export type ActionKind = "dryRun" | "simulate" | "live";

export type ActionPhase = "idle" | "running" | "success" | "error";

export interface ActionFeedback {
  kind: ActionKind;
  phase: ActionPhase;
  title: string;
  message: string;
  detail?: string;
}

export const INITIAL_PIPELINE: Record<PipelineStepId, StepStatus> = {
  upload: "waiting",
  analyze: "waiting",
  compile: "waiting",
  simulate: "waiting",
  send: "waiting",
};

/** Yeni dosya seçildiğinde: Plan Yükle hazır, diğer aşamalar bekliyor. */
export function pipelineAfterFileSelect(): Record<PipelineStepId, StepStatus> {
  return {
    upload: "ready",
    analyze: "waiting",
    compile: "waiting",
    simulate: "waiting",
    send: "waiting",
  };
}

/** Derleme sonrası pipeline — simülasyon ve canlı gönderim sıfırlanır. */
export function pipelineAfterCompile(penSafe: boolean): Record<PipelineStepId, StepStatus> {
  return {
    upload: "success",
    analyze: "success",
    compile: penSafe ? "success" : "error",
    simulate: "waiting",
    send: "waiting",
  };
}

export function formatActivityLog(level: LogLevel, message: string): string {
  return `[${level}] ${message}`;
}

export function parseActivityLogLevel(line: string): LogLevel | null {
  const match = line.match(/^\[(INFO|OK|SIM|DRY|ERR)\]/);
  return match ? (match[1] as LogLevel) : null;
}

export function newPlanActivityLog(fileName: string): string[] {
  return [formatActivityLog("INFO", `Yeni plan seçildi: ${fileName}`)];
}

/** Yeni plan seçildiğinde uygulanacak tam workflow sıfırlama paketi (test edilebilir). */
export interface PlanResetPatch {
  commandsText: string;
  walls: number[][];
  pathPoints: number[][];
  preflight: null;
  planName: null;
  pipeline: Record<PipelineStepId, StepStatus>;
  penSafeKnown: boolean;
  penSafe: boolean;
  simJobId: null;
  serialMode: null;
  activeMode: "idle";
  actionFeedback: null;
  activityLog: string[];
}

export function buildPlanResetPatch(fileName: string): PlanResetPatch {
  return {
    commandsText: "",
    walls: [],
    pathPoints: [],
    preflight: null,
    planName: null,
    pipeline: pipelineAfterFileSelect(),
    penSafeKnown: false,
    penSafe: false,
    simJobId: null,
    serialMode: null,
    activeMode: "idle",
    actionFeedback: null,
    activityLog: newPlanActivityLog(fileName),
  };
}

/** Derleme başlangıcında dry-run/sim/live türev adımlarını sıfırlar. */
export function pipelineAfterDerivedReset(): Record<PipelineStepId, StepStatus> {
  return {
    upload: "ready",
    analyze: "waiting",
    compile: "waiting",
    simulate: "waiting",
    send: "waiting",
  };
}

export function nextPlanSessionId(current: number): number {
  return current + 1;
}

export function isPlanSessionCurrent(expected: number, actual: number): boolean {
  return expected === actual;
}

export function isDryRunSuccess(res: ExecuteSerialResponse): boolean {
  if (res.ok === false) return false;
  if (res.ok === true) return true;
  const status = (res.status ?? "").toLowerCase();
  return status === "completed" || status === "dry_run" || status === "success" || status === "ok";
}

export function buildDryRunFeedback(
  phase: ActionPhase,
  res?: ExecuteSerialResponse,
  errorMessage?: string,
): ActionFeedback {
  if (phase === "running") {
    return {
      kind: "dryRun",
      phase,
      title: "Dry-run",
      message: "Komutlar test ediliyor…",
    };
  }
  if (phase === "error") {
    return {
      kind: "dryRun",
      phase,
      title: "Dry-run",
      message: errorMessage ?? "Dry-run başarısız",
    };
  }
  const count = res?.command_count;
  const backendMsg = res?.message?.trim();
  const detailParts: string[] = [];
  if (backendMsg) detailParts.push(backendMsg);
  if (count != null) detailParts.push(`${count} komut doğrulandı`);
  return {
    kind: "dryRun",
    phase: "success",
    title: "Dry-run tamamlandı",
    message: "Komutlar robota gönderilmeden doğrulandı.",
    detail: detailParts.length ? detailParts.join(" · ") : undefined,
  };
}

export function buildSimFeedback(
  phase: ActionPhase,
  jobId?: string,
  errorMessage?: string,
): ActionFeedback {
  if (phase === "running") {
    return {
      kind: "simulate",
      phase,
      title: "Simülasyon",
      message: "Simülasyon işi oluşturuluyor…",
    };
  }
  if (phase === "error") {
    return {
      kind: "simulate",
      phase,
      title: "Simülasyon",
      message: errorMessage ?? "Simülasyon başlatılamadı",
    };
  }
  return {
    kind: "simulate",
    phase: "success",
    title: "Simülasyon işi oluşturuldu",
    message: jobId ? `job_id=${jobId}` : "Simülasyon işi oluşturuldu",
    detail:
      "Canlı animasyon henüz bağlı değil; bu adım şimdilik job oluşturma doğrulamasıdır.",
  };
}

export function buildLiveFeedback(
  phase: ActionPhase,
  res?: ExecuteSerialResponse,
  errorMessage?: string,
): ActionFeedback {
  if (phase === "running") {
    return {
      kind: "live",
      phase,
      title: "Canlı gönderim",
      message: "Komutlar seri porta gönderiliyor…",
    };
  }
  if (phase === "error") {
    return {
      kind: "live",
      phase,
      title: "Canlı gönderim",
      message: errorMessage ?? "Canlı gönderim başarısız",
    };
  }
  return {
    kind: "live",
    phase: "success",
    title: "Canlı gönderim",
    message: res?.message ?? "Gönderim tamamlandı",
    detail: res?.status ? `Durum: ${res.status}` : undefined,
  };
}

export function formatSimLog(jobId: string): string {
  return formatActivityLog("SIM", `Simülasyon işi oluşturuldu: job_id=${jobId}`);
}

export function formatDryRunLog(success: boolean, detail?: string): string {
  if (success) {
    return formatActivityLog(
      "OK",
      detail
        ? `Dry-run tamamlandı: komutlar robota gönderilmeden doğrulandı. ${detail}`
        : "Dry-run tamamlandı: komutlar robota gönderilmeden doğrulandı.",
    );
  }
  return formatActivityLog("ERR", detail ?? "Dry-run başarısız");
}

export function formatLiveLog(success: boolean, detail: string): string {
  return formatActivityLog(success ? "OK" : "ERR", `Canlı gönderim: ${detail}`);
}
