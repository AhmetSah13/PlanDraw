import type {
  AnalyzeResponse,
  AnalyzeStats,
  CompilePlanRequest,
  CompilePlanResponse,
  DiagnosticRecord,
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

function mapExecuteSerialErrorCode(code: string | null | undefined): string | null {
  switch (code) {
    case "SERIAL_PORT_MISSING":
      return "Seri port ayarlı değil (SERIAL_PORT env eksik).";
    case "INVALID_SERIAL_BAUD":
      return "Seri port baud ayarı geçersiz (SERIAL_BAUD).";
    default:
      return null;
  }
}

/** Kullanıcıya gösterilecek Türkçe hata metni. */
export function formatUserError(error: unknown): string {
  if (error instanceof ApiError) {
    const row = asRecord(error.data);
    const mapped =
      mapExecuteSerialErrorCode(
        typeof row.error_detail === "string"
          ? row.error_detail
          : typeof row.error_code === "string"
            ? row.error_code
            : null,
      ) ?? mapExecuteSerialErrorCode(
        typeof row.detail === "string" ? row.detail : null,
      );
    if (mapped) return mapped;
    return error.message;
  }
  if (error instanceof TypeError) {
    return "Backend bağlantısı kurulamadı. Sunucunun çalıştığını kontrol edin.";
  }
  if (error instanceof SyntaxError) {
    return "JSON plan dosyası okunamadı. Geçerli bir plan dosyası seçin.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Beklenmeyen bir hata oluştu.";
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { ham: text };
  }
}

/** FastAPI 422 validation detail → kısa Türkçe özet. */
export function formatValidationDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (!Array.isArray(detail)) return null;

  const parts = detail
    .map((item) => {
      const row = asRecord(item);
      const loc = Array.isArray(row.loc)
        ? row.loc.filter((p) => p !== "body").join(".")
        : "";
      const msg = typeof row.msg === "string" ? row.msg : "";
      if (!msg) return "";
      return loc ? `${loc}: ${msg}` : msg;
    })
    .filter(Boolean);

  return parts.length ? parts.slice(0, 3).join("; ") : null;
}

function resolveError(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null) {
    const row = data as Record<string, unknown>;
    const mapped = mapExecuteSerialErrorCode(
      typeof row.error_detail === "string" ? row.error_detail : null,
    );
    if (mapped) return mapped;

    const validation = formatValidationDetail(row.detail);
    if (validation) {
      if (status === 422) return `Backend doğrulama hatası: ${validation}`;
      return validation;
    }

    const detail = row.detail ?? row.error ?? row.message;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  if (status === 403) return "Erişim reddedildi (execute_serial güvenlik kısıtı).";
  if (status === 409) return "Seri port meşgul — eşzamanlı canlı gönderim yapılamıyor.";
  if (status === 422) return "İstek geçersiz — backend şema doğrulaması başarısız.";
  if (status >= 500) return "Sunucu hatası. Backend loglarını kontrol edin.";
  return `İstek başarısız (HTTP ${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new TypeError("network");
  }
  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(resolveError(data, response.status), response.status, data);
  }
  return data as T;
}

async function getJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function postForm<T>(path: string, body: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body });
}

function asRecord(data: unknown): Record<string, unknown> {
  return typeof data === "object" && data !== null ? (data as Record<string, unknown>) : {};
}

/** Import/compile yanıtından komut metnini güvenli çıkarır. */
export function extractCommandsText(res: ImportPlanResponse | CompilePlanResponse): string {
  const row = asRecord(res);
  const candidates = [
    row.commands_text_optimized,
    row.commands_text_raw,
    row.commands_text,
  ];
  for (const c of candidates) {
    if (typeof c === "string" && c.trim()) return c;
  }
  return "";
}

function normalizePathPoints(raw: unknown): number[][] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((p) => Array.isArray(p) && p.length >= 2)
    .map((p) => [Number(p[0]), Number(p[1])])
    .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
}

function normalizeWalls(raw: unknown): number[][] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((w) => Array.isArray(w) && w.length >= 4)
    .map((w) => w.slice(0, 4).map(Number))
    .filter((w) => w.every(Number.isFinite));
}

export function normalizeImportResponse(data: unknown): ImportPlanResponse {
  const row = asRecord(data);
  return {
    ok: row.ok === true,
    error: typeof row.error === "string" ? row.error : row.error === null ? null : undefined,
    warnings: Array.isArray(row.warnings) ? row.warnings.map(String) : [],
    commands_text: typeof row.commands_text === "string" ? row.commands_text : undefined,
    commands_text_raw: typeof row.commands_text_raw === "string" ? row.commands_text_raw : undefined,
    commands_text_optimized:
      typeof row.commands_text_optimized === "string" ? row.commands_text_optimized : undefined,
    plan_text: typeof row.plan_text === "string" ? row.plan_text : undefined,
    walls: normalizeWalls(row.walls),
    raw_path_points: normalizePathPoints(row.raw_path_points),
    stats: typeof row.stats === "object" && row.stats !== null ? (row.stats as ImportPlanResponse["stats"]) : undefined,
  };
}

export async function fetchHealth(): Promise<HealthResponse> {
  const data = await getJson<unknown>("/health");
  const row = asRecord(data);
  return { ok: row.ok === true };
}

export async function fetchStatus(): Promise<StatusResponse> {
  const data = await getJson<unknown>("/api/status");
  const row = asRecord(data);
  return {
    ok: row.ok === true,
    dwg_converter_available: row.dwg_converter_available === true,
    dwg_converter_reason:
      typeof row.dwg_converter_reason === "string" ? row.dwg_converter_reason : undefined,
  };
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
  const data = await postForm<unknown>("/api/import_dxf", form);
  return normalizeImportResponse(data);
}

export async function importPlanJson(file: File): Promise<ImportPlanResponse> {
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(await file.text()) as Record<string, unknown>;
  } catch {
    throw new SyntaxError("invalid json");
  }
  const data = await postJson<unknown>("/api/import_plan", {
    return_commands_text: true,
    return_plan_text: true,
    return_raw_path: true,
    ...payload,
  });
  return normalizeImportResponse(data);
}

export async function compilePlan(req: CompilePlanRequest): Promise<CompilePlanResponse> {
  const data = await postJson<unknown>("/api/compile_plan", req);
  const row = asRecord(data);
  return {
    ok: row.ok === true,
    error: typeof row.error === "string" ? row.error : undefined,
    commands_text: typeof row.commands_text === "string" ? row.commands_text : undefined,
    commands_text_raw: typeof row.commands_text_raw === "string" ? row.commands_text_raw : undefined,
    commands_text_optimized:
      typeof row.commands_text_optimized === "string" ? row.commands_text_optimized : undefined,
    raw_path_points: normalizePathPoints(row.raw_path_points),
    walls: normalizeWalls(row.walls),
    stats: typeof row.stats === "object" && row.stats !== null ? (row.stats as CompilePlanResponse["stats"]) : undefined,
  };
}

function normalizeDiagnostics(raw: unknown): DiagnosticRecord[] {
  if (!Array.isArray(raw)) return [];
  const out: DiagnosticRecord[] = [];
  for (const item of raw) {
    const row = asRecord(item);
    const severity: DiagnosticRecord["severity"] =
      row.severity === "ERROR" || row.severity === "WARN" ? row.severity : "WARN";
    const record: DiagnosticRecord = {
      severity,
      line: typeof row.line === "number" ? row.line : 0,
      message: typeof row.message === "string" ? row.message : "",
      text: typeof row.text === "string" ? row.text : "",
    };
    if (record.message || record.text) out.push(record);
  }
  return out;
}

function normalizeAnalyzeStats(raw: unknown): AnalyzeStats {
  const row = asRecord(raw);
  return {
    move_count: typeof row.move_count === "number" ? row.move_count : 0,
    wait_total: typeof row.wait_total === "number" ? row.wait_total : 0,
    path_length: typeof row.path_length === "number" ? row.path_length : 0,
    estimated_time: typeof row.estimated_time === "number" ? row.estimated_time : undefined,
    collision_count: typeof row.collision_count === "number" ? row.collision_count : 0,
    wall_overlap_count: typeof row.wall_overlap_count === "number" ? row.wall_overlap_count : 0,
    wall_touch_count: typeof row.wall_touch_count === "number" ? row.wall_touch_count : 0,
    wall_proper_cross_count:
      typeof row.wall_proper_cross_count === "number" ? row.wall_proper_cross_count : 0,
  };
}

/** Backend /api/analyze yanıtını ExecuteSerialRequest.preflight şemasına uygun normalize eder. */
export function normalizeAnalyzeResponse(data: unknown): AnalyzeResponse {
  const row = asRecord(data);
  return {
    blocked: row.blocked === true,
    commands_unrolled: typeof row.commands_unrolled === "string" ? row.commands_unrolled : "",
    parser: normalizeDiagnostics(row.parser),
    analysis: normalizeDiagnostics(row.analysis),
    stats: normalizeAnalyzeStats(row.stats),
  };
}

export async function analyzeCommands(
  commandsText: string,
  walls?: number[][],
  collisionMode: "warn" | "error" = "warn",
): Promise<AnalyzeResponse> {
  const data = await postJson<unknown>("/api/analyze", buildAnalyzePayload(commandsText, walls, collisionMode));
  return normalizeAnalyzeResponse(data);
}

export function buildAnalyzePayload(
  commandsText: string,
  walls?: number[][],
  collisionMode: "warn" | "error" = "warn",
): Record<string, unknown> {
  return {
    commands_text: commandsText,
    walls,
    collision_mode: collisionMode,
  };
}

export interface ExecuteSerialOptions {
  dryRun: boolean;
  walls?: number[][];
  preflight?: AnalyzeResponse;
}

/**
 * POST /api/execute_serial gövdesi — backend ExecuteSerialRequest ile uyumlu.
 * dry_run=true iken preflight gönderilmez (eksik AnalyzeResponse 422 üretir).
 */
export function buildExecuteSerialPayload(
  text: string,
  options: ExecuteSerialOptions,
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    text,
    dry_run: options.dryRun,
  };
  if (options.walls?.length) {
    body.walls = options.walls;
  }
  if (!options.dryRun && options.preflight) {
    body.preflight = options.preflight;
  }
  return body;
}

export async function executeSerial(
  text: string,
  options: ExecuteSerialOptions,
): Promise<ExecuteSerialResponse> {
  const data = await postJson<unknown>(
    "/api/execute_serial",
    buildExecuteSerialPayload(text, options),
  );
  return normalizeExecuteResponse(data);
}

export async function stopLiveSerial(): Promise<ExecuteSerialResponse> {
  const data = await postJson<unknown>("/api/execute_serial/stop", {});
  return normalizeExecuteResponse(data);
}

function normalizeExecuteResponse(data: unknown): ExecuteSerialResponse {
  const row = asRecord(data);
  return {
    status: typeof row.status === "string" ? row.status : "unknown",
    message: typeof row.message === "string" ? row.message : "Yanıt mesajı yok",
    command_count: typeof row.command_count === "number" ? row.command_count : undefined,
    ok: row.ok === true ? true : row.ok === false ? false : undefined,
    stopped: row.stopped === true ? true : row.stopped === false ? false : undefined,
    mode: typeof row.mode === "string" ? row.mode : undefined,
    error_code: typeof row.error_code === "string" ? row.error_code : null,
    error_detail: typeof row.error_detail === "string" ? row.error_detail : null,
    notes: Array.isArray(row.notes) ? row.notes.map(String) : undefined,
    trace_id: typeof row.trace_id === "string" ? row.trace_id : null,
  };
}

export async function createSimulationJob(
  text: string,
  walls?: number[][],
): Promise<SimulationJobResponse> {
  const data = await postJson<unknown>("/api/jobs", {
    text,
    dt: 0.016,
    speed_multiplier: 1,
    walls,
  });
  const row = asRecord(data);
  const jobId = row.job_id;
  if (typeof jobId !== "string" || !jobId.trim()) {
    throw new ApiError("Simülasyon job_id alınamadı.", 500, data);
  }
  return { job_id: jobId };
}

export async function stopSimulationJob(jobId: string): Promise<JobStopResponse> {
  const data = await postJson<unknown>(`/api/jobs/${encodeURIComponent(jobId)}/stop`, {});
  const row = asRecord(data);
  return {
    stopped: row.stopped === true,
    error: typeof row.error === "string" ? row.error : undefined,
  };
}

export function buildSimulationStreamUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/stream`;
}

export function isSupportedPlanFile(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ext === "dxf" || ext === "json";
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
