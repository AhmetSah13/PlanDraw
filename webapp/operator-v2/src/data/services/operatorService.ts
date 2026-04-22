import { apiBaseUrl, postForm, postJson } from "../http/apiClient";

export interface HealthStatus {
  ok?: boolean;
  status?: string;
  [key: string]: unknown;
}

export interface ImportPlanPayload {
  version: string;
  units: string;
  scale: number;
  origin: { x: number; y: number };
  segments: Array<{ x1: number; y1: number; x2: number; y2: number }>;
}

export interface PlanHazirlamaYaniti {
  ok?: boolean;
  error?: string | null;
  warnings?: string[];
  commands_text?: string;
  commands_text_raw?: string;
  commands_text_optimized?: string;
  plan_text?: string;
  walls?: number[][];
  raw_path_points?: number[][];
  recommended_step_size?: number;
  stats?: {
    path_points?: number[][];
    move_count?: number;
    path_length?: number;
    estimated_time?: number;
  };
  [key: string]: unknown;
}

export interface TaniKaydi {
  severity: string;
  line: number;
  message: string;
  text: string;
}

export interface IstatistikOzeti {
  move_count?: number;
  wait_total?: number;
  path_length?: number;
  estimated_time?: number;
  path_points?: number[][];
  original_move_count?: number;
  optimized_move_count?: number;
  reduction_ratio?: number;
  collision_count?: number;
  wall_overlap_count?: number;
  wall_touch_count?: number;
  wall_proper_cross_count?: number;
}

export interface AnalyzeYaniti {
  blocked: boolean;
  commands_unrolled: string;
  parser: TaniKaydi[];
  analysis: TaniKaydi[];
  stats: IstatistikOzeti;
}

export interface KontrolNoktasiPayload {
  cad_x: number;
  cad_y: number;
  site_x: number;
  site_y: number;
  label?: string;
  weight?: number;
}

export interface HizalamaPayload {
  walls: number[][];
  control_points: KontrolNoktasiPayload[];
  tolerance_m: number;
}

export interface HizalamaYaniti {
  ok: boolean;
  error?: string;
  alignment?: {
    transform_type: string;
    point_count: number;
    residual_mean_m: number;
    residual_max_m: number;
    tolerance_m: number;
    blocked: boolean;
    transform: {
      theta_rad: number;
      theta_deg: number;
      tx_m: number;
      ty_m: number;
    };
    reasons: string[];
    notes: string[];
  };
  pre_svg?: string;
  post_svg?: string;
}

export interface SimulasyonIsYanit {
  job_id: string;
}

export interface SimulasyonOlusturmaSecenekleri {
  dt?: number;
  speedMultiplier?: number;
  walls?: number[][];
}

export interface SerialCalistirmaYaniti {
  status: string;
  message: string;
  command_count: number;
  driver_status?: Record<string, unknown> | null;
  error_detail?: string | null;
  artifact_paths: string[];
  notes: string[];
}

export interface SerialCalistirmaSecenekleri {
  dryRun: boolean;
}

export interface IsDurdurmaYaniti {
  stopped?: boolean;
  error?: string;
}

export interface ExportSecenekleri {
  format?: "robot_v1" | "gcode_lite";
}

export interface ExportYaniti {
  ok: boolean;
  blocked: boolean;
  content: string;
  filename: string;
  parser_diags: TaniKaydi[];
  analysis_diags: TaniKaydi[];
  stats: IstatistikOzeti;
}

export function importPlan(payload: ImportPlanPayload) {
  return postJson("/api/import_plan", payload);
}

export function importPlanJsonPayload(payload: Record<string, unknown>) {
  return postJson<PlanHazirlamaYaniti>("/api/import_plan", {
    return_commands_text: true,
    return_plan_text: true,
    return_raw_path: true,
    ...payload
  });
}

export function importDxfDosyasi(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append(
    "options_json",
    JSON.stringify({
      return_raw_path: true
    }),
  );
  return postForm<PlanHazirlamaYaniti>("/api/import_dxf", formData);
}

export function importDwgDosyasi(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append(
    "options_json",
    JSON.stringify({
      return_raw_path: true
    }),
  );
  return postForm<PlanHazirlamaYaniti>("/api/import_dwg", formData);
}

export async function importJsonDosyasi(file: File) {
  const text = await file.text();
  let payload: Record<string, unknown>;

  try {
    payload = JSON.parse(text) as Record<string, unknown>;
  } catch {
    throw new Error("JSON dosyası okunamadı. Geçerli bir plan dosyası seçin.");
  }

  return importPlanJsonPayload(payload);
}

export function compilePlanText(planText: string) {
  return postJson<PlanHazirlamaYaniti>("/api/compile_plan", {
    plan_text: planText
  });
}

export function analyzeCommands(commandsText: string, walls?: number[][]) {
  return postJson<AnalyzeYaniti>("/api/analyze", {
    commands_text: commandsText,
    walls,
    collision_mode: "warn"
  });
}

export function alignRigidLayout(payload: HizalamaPayload) {
  return postJson<HizalamaYaniti>("/api/alignment/rigid_2d", payload);
}

export function createSimulationJob(
  text: string,
  options: SimulasyonOlusturmaSecenekleri = {},
) {
  return postJson<SimulasyonIsYanit>("/api/jobs", {
    text,
    dt: options.dt ?? 0.016,
    speed_multiplier: options.speedMultiplier ?? 1,
    walls: options.walls,
  });
}

export function buildSimulationStreamUrl(jobId: string) {
  return `${apiBaseUrl()}/api/jobs/${jobId}/stream`;
}

export function stopSimulationJob(jobId: string) {
  return postJson<IsDurdurmaYaniti>(`/api/jobs/${jobId}/stop`, {});
}

export function executeSerialRun(
  text: string,
  options: SerialCalistirmaSecenekleri,
) {
  return postJson<SerialCalistirmaYaniti>("/api/execute_serial", {
    text,
    dry_run: options.dryRun,
  });
}

export function exportCommands(
  text: string,
  options: ExportSecenekleri = {},
) {
  return postJson<ExportYaniti>("/api/export", {
    text,
    format: options.format ?? "robot_v1"
  });
}
