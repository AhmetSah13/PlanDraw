const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export async function analyzeScenario(commandsText, start = null, optimize = null, walls = null, collisionMode = "warn") {
  const body = { commands_text: commandsText, start, collision_mode: collisionMode };
  if (optimize != null) body.optimize = optimize;
  if (walls != null) body.walls = walls;
  const res = await fetch(`${BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Analyze failed");
  }
  return await res.json();
}

/**
 * SSE event bloğunu parse eder. "\n\n" ile ayrılmış bloklar için.
 * rawEvent satırları: event: X, data: Y (çok satırlı data birleştirilir).
 * @returns { { eventName: string, payload: object } | null }
 */
function parseSSEEvent(rawEvent) {
  let eventName = "message";
  const dataLines = [];
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  const dataStr = dataLines.join("\n");
  if (!dataStr) return null;
  try {
    return { eventName, payload: JSON.parse(dataStr) };
  } catch {
    return null;
  }
}

/**
 * Simülasyon başlatır. 409 ise { ok: false, blocked: true, parser_diags, analysis_diags, stats } döner.
 * 200 ise stream okunur ve onEvent(eventName, payload) her SSE event için çağrılır (tick, done, error).
 * @param {AbortSignal} [signal] - İptal için
 * @param {function(string, object)} [onEvent] - (eventName, payload) callback
 */
export async function simulateScenario(script, options = {}, signal = null, onEvent = null) {
  const { dt = 0.016, speed_multiplier = 1.0, start = [0, 0] } = options;
  const res = await fetch(`${BASE}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: script, dt, speed_multiplier, start }),
    signal
  });
  if (res.status === 409) {
    const data = await res.json();
    return { ok: false, ...data };
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Simulate failed");
  }
  if (!onEvent) {
    return { ok: true, response: res };
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const parsed = parseSSEEvent(rawEvent);
      if (parsed) onEvent(parsed.eventName, parsed.payload);
    }
  }
  if (buffer.trim()) {
    const parsed = parseSSEEvent(buffer);
    if (parsed) onEvent(parsed.eventName, parsed.payload);
  }
  return { ok: true };
}

/**
 * Job oluşturur. 409 ise { ok: false, blocked: true, ... }. 200 ise { ok: true, job_id }.
 */
export async function createJob(script, options = {}) {
  const { dt = 0.016, speed_multiplier = 1.0, start = [0, 0], optimize = null, motion = null, walls = null, collisionMode = "warn" } = options;
  const body = { text: script, dt, speed_multiplier, start, collision_mode: collisionMode };
  if (optimize != null) body.optimize = optimize;
  if (motion != null) body.motion = motion;
  if (walls != null) body.walls = walls;
  const res = await fetch(`${BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_) {}
  if (res.status === 409) return { ok: false, ...data };
  if (!res.ok) throw new Error(data.detail || data.error || text || `HTTP ${res.status}`);
  return { ok: true, job_id: data.job_id };
}

/**
 * Job stream'ine bağlanır, onEvent ile tick/done/error çağrılır. signal ile iptal.
 */
export async function getJobStream(jobId, onEvent, signal = null) {
  const res = await fetch(`${BASE}/api/jobs/${jobId}/stream`, { signal });
  if (!res.ok) throw new Error("Stream failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const parsed = parseSSEEvent(rawEvent);
      if (parsed && parsed.eventName) onEvent(parsed.eventName, parsed.payload);
    }
  }
  if (buffer.trim()) {
    const parsed = parseSSEEvent(buffer);
    if (parsed && parsed.eventName) onEvent(parsed.eventName, parsed.payload);
  }
}

export async function stopJob(jobId) {
  const res = await fetch(`${BASE}/api/jobs/${jobId}/stop`, { method: "POST" });
  if (!res.ok) return;
  await res.json();
}

/**
 * Plan metninden script üretir.
 * Body: plan_text, step_size, speed, world_scale, world_offset
 * Return: { ok, error?, raw_path_points?, commands_text, stats, parser_diags, analysis_diags }
 */
export async function compilePlan(planText, options = {}) {
  const {
    step_size = 5.0,
    speed = 120.0,
    world_scale = 1.0,
    world_offset = [0, 0],
    optimize = null
  } = options;
  const body = { plan_text: planText, step_size, speed, world_scale, world_offset };
  if (optimize != null) body.optimize = optimize;
  const res = await fetch(`${BASE}/api/compile_plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
    throw new Error("Geçersiz yanıt");
  }
  if (!res.ok) {
    const msg = (data.detail ?? data.error ?? text) || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

/**
 * Robot export (W6). Body: text, start, format (robot_v1 | gcode_lite), optimize (optional).
 * Return: { ok, blocked, content, filename, parser_diags, analysis_diags, stats }
 */
export async function exportRobot(script, options = {}) {
  const { start = [0, 0], format = "robot_v1", optimize = null } = options;
  const body = { text: script, start, format };
  if (optimize != null) body.optimize = optimize;
  const res = await fetch(`${BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
    throw new Error("Geçersiz yanıt");
  }
  if (!res.ok) {
    const msg = (data.detail ?? data.error ?? text) || `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

/**
 * JSON plan dosyasını içe aktarır (M4). POST /api/import_plan.
 * Return: { ok, error?, normalized?, warnings?, plan_text?, commands_text?, walls?, raw_path_points? }
 */
export async function importPlanFromJson(payload) {
  const res = await fetch(`${BASE}/api/import_plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || "Import yanıtı parse edilemedi");
  }
  return data;
}

/**
 * DXF dosyasını içe aktarır. POST /api/import_dxf (multipart).
 * @param {File} file - .dxf dosyası
 * @param {object} options - ImportDxfOptions alanları (normalize, return_* bayrakları, step_size, speed, preview_layers, selected_layers, auto_step_target_moves vb.)
 * Return: { ok, error?, normalized?, warnings?, plan_text?, commands_text?, walls?, raw_path_points?, layers?, suggested_layers?, recommended_step_size? }
 */
export async function importDxf(file, options) {
  const form = new FormData();
  form.append("file", file);
  form.append("options_json", JSON.stringify(options));
  const res = await fetch(`${BASE}/api/import_dxf`, {
    method: "POST",
    body: form
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || "DXF import yanıtı parse edilemedi");
  }
  return data;
}

/**
 * DWG dosyasını içe aktarır. POST /api/import_dwg (multipart). Backend DWG→DXF dönüştürücü kullanır.
 * @param {File} file - .dwg dosyası
 * @param {object} options - ImportDxfOptions ile aynı (normalize, return_*, step_size, speed, preview_layers, selected_layers, auto_step_target_moves vb.)
 * Return: { ok, error?, normalized?, warnings?, plan_text?, commands_text?, walls?, raw_path_points?, layers?, suggested_layers?, recommended_step_size? }
 */
export async function importDwg(file, options) {
  const form = new FormData();
  form.append("file", file);
  form.append("options_json", JSON.stringify(options));
  const res = await fetch(`${BASE}/api/import_dwg`, {
    method: "POST",
    body: form
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || "DWG import yanıtı parse edilemedi");
  }
  return data;
}
