import type {
  AnalyzeResponse,
  CompilePlanRequest,
  CompilePlanResponse,
  ExecuteSerialResponse,
  HealthResponse,
  ImportPlanResponse,
  JobStopResponse,
  SimulationJobResponse,
  StatusResponse,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { ham: text };
  }
}

function resolveError(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null) {
    const row = data as Record<string, unknown>;
    const detail = row.detail ?? row.error ?? row.message;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return `HTTP ${status}`;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(resolveError(data, response.status), response.status, data);
  }
  return data as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(resolveError(data, response.status), response.status, data);
  }
  return data as T;
}

async function postForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body });
  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(resolveError(data, response.status), response.status, data);
  }
  return data as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export async function fetchStatus(): Promise<StatusResponse> {
  return getJson<StatusResponse>("/api/status");
}

export async function importDxf(file: File): Promise<ImportPlanResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append(
    "options_json",
    JSON.stringify({
      return_commands_text: true,
      return_plan_text: true,
      return_raw_path: true,
    }),
  );
  return postForm<ImportPlanResponse>("/api/import_dxf", form);
}

export async function importPlanJson(file: File): Promise<ImportPlanResponse> {
  const text = await file.text();
  const payload = JSON.parse(text) as Record<string, unknown>;
  return postJson<ImportPlanResponse>("/api/import_plan", {
    return_commands_text: true,
    return_plan_text: true,
    return_raw_path: true,
    ...payload,
  });
}

export async function compilePlan(req: CompilePlanRequest): Promise<CompilePlanResponse> {
  return postJson<CompilePlanResponse>("/api/compile_plan", req);
}

export async function analyzeCommands(
  commandsText: string,
  walls?: number[][],
): Promise<AnalyzeResponse> {
  return postJson<AnalyzeResponse>("/api/analyze", {
    commands_text: commandsText,
    walls,
    collision_mode: "warn",
  });
}

export async function executeSerial(
  text: string,
  options: { dryRun: boolean; walls?: number[][]; preflight?: AnalyzeResponse },
): Promise<ExecuteSerialResponse> {
  return postJson<ExecuteSerialResponse>("/api/execute_serial", {
    text,
    dry_run: options.dryRun,
    walls: options.walls,
    preflight: options.preflight,
  });
}

export async function stopLiveSerial(): Promise<ExecuteSerialResponse> {
  return postJson<ExecuteSerialResponse>("/api/execute_serial/stop", {});
}

export async function createSimulationJob(
  text: string,
  walls?: number[][],
): Promise<SimulationJobResponse> {
  return postJson<SimulationJobResponse>("/api/jobs", {
    text,
    dt: 0.016,
    speed_multiplier: 1,
    walls,
  });
}

export async function stopSimulationJob(jobId: string): Promise<JobStopResponse> {
  return postJson<JobStopResponse>(`/api/jobs/${jobId}/stop`, {});
}

export function buildSimulationStreamUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/stream`;
}

/** Pen-safe gramer kontrolü (istemci tarafı özet). */
export function isPenSafeCommands(text: string): boolean {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length) return false;
  const penUps = lines.filter((l) => /^PEN\s+UP$/i.test(l)).length;
  const penDowns = lines.filter((l) => /^PEN\s+DOWN$/i.test(l)).length;
  if (penDowns === 0) return false;
  const lastPen = [...lines].reverse().find((l) => /^PEN\s+(UP|DOWN)$/i.test(l));
  return penUps >= penDowns && lastPen?.toUpperCase() === "PEN UP";
}

export function countStrokes(text: string): number {
  return text.split("\n").filter((l) => /^PEN\s+DOWN$/i.test(l.trim())).length;
}

export function countMoves(text: string): number {
  return text.split("\n").filter((l) => /^MOVE\s+/i.test(l.trim())).length;
}
