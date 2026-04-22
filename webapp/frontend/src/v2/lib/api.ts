const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const EXECUTE_TOKEN = import.meta.env.VITE_EXECUTE_SERIAL_TOKEN ?? "";

async function readJson(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
}

async function postJson<T>(path: string, body: unknown, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const data = await readJson(res);
  if (!res.ok) {
    throw new Error(String(data?.detail ?? data?.error ?? data?.message ?? `HTTP ${res.status}`));
  }
  return data as T;
}

export async function importPlanJson(payload: unknown) {
  return postJson("/api/import_plan", payload);
}

export async function importDxf(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/api/import_dxf`, { method: "POST", body: fd });
  const data = await readJson(res);
  if (!res.ok) throw new Error(String(data?.detail ?? data?.error ?? `HTTP ${res.status}`));
  return data;
}

export async function importDwg(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/api/import_dwg`, { method: "POST", body: fd });
  const data = await readJson(res);
  if (!res.ok) throw new Error(String(data?.detail ?? data?.error ?? `HTTP ${res.status}`));
  return data;
}

export async function compilePlan(planText: string) {
  return postJson("/api/compile_plan", { plan_text: planText });
}

export async function hizala(payload: unknown) {
  return postJson("/api/alignment/rigid_2d", payload);
}

export async function analizEt(commandsText: string) {
  return postJson("/api/analyze", { commands_text: commandsText });
}

export async function jobOlustur(text: string) {
  return postJson<{ job_id: string }>("/api/jobs", { text });
}

export async function jobDurdur(jobId: string) {
  return postJson("/api/jobs/" + encodeURIComponent(jobId) + "/stop", {});
}

export async function seriCalistir(text: string, dryRun: boolean) {
  const headers: Record<string, string> = {};
  if (EXECUTE_TOKEN.trim()) headers["X-Execute-Token"] = EXECUTE_TOKEN;
  return postJson("/api/execute_serial", { text, dry_run: dryRun }, headers);
}

export function streamUrl(jobId: string) {
  return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/stream`;
}
