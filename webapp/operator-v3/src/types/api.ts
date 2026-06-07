export interface HealthResponse {
  ok?: boolean;
}

export interface StatusResponse {
  ok?: boolean;
  dwg_converter_available?: boolean;
  dwg_converter_reason?: string;
}

export interface CompileStats {
  move_count?: number;
  path_length?: number;
  estimated_time?: number;
  path_points?: number[][];
}

export interface ImportPlanResponse {
  ok?: boolean;
  error?: string | null;
  warnings?: string[];
  commands_text?: string;
  commands_text_raw?: string;
  commands_text_optimized?: string;
  plan_text?: string;
  walls?: number[][];
  raw_path_points?: number[][];
  stats?: CompileStats;
}

export interface CompilePlanRequest {
  plan_text: string;
  step_size?: number;
  speed?: number;
  world_scale?: number;
  world_offset?: [number, number] | null;
}

export interface CompilePlanResponse {
  ok?: boolean;
  error?: string;
  commands_text?: string;
  commands_text_raw?: string;
  commands_text_optimized?: string;
  raw_path_points?: number[][];
  walls?: number[][];
  stats?: CompileStats;
}

export interface AnalyzeResponse {
  blocked: boolean;
  commands_unrolled: string;
  stats: CompileStats;
}

export interface ExecuteSerialResponse {
  status: string;
  message: string;
  command_count?: number;
  ok?: boolean;
  stopped?: boolean;
  mode?: string;
  error_code?: string | null;
  error_detail?: string | null;
  notes?: string[];
  trace_id?: string | null;
}

export interface SimulationJobResponse {
  job_id: string;
}

export interface JobStopResponse {
  stopped?: boolean;
  error?: string;
}

export type ConnectionState = "online" | "offline" | "checking";
