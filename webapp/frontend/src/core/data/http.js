const BASE_URL = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const EXECUTE_SERIAL_TOKEN = import.meta.env.VITE_EXECUTE_SERIAL_TOKEN ?? null;

function withBase(path) {
  return `${BASE_URL}${path}`;
}

async function readBody(res) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
}

export async function httpJson(path, { method = "GET", body, headers = {} } = {}) {
  const res = await fetch(withBase(path), {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body != null ? JSON.stringify(body) : undefined,
  });
  const data = await readBody(res);
  if (!res.ok) {
    const msg = data?.detail ?? data?.error ?? data?.message ?? `HTTP ${res.status}`;
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

export async function httpForm(path, formData) {
  const res = await fetch(withBase(path), {
    method: "POST",
    body: formData,
  });
  const data = await readBody(res);
  if (!res.ok) {
    const msg = data?.detail ?? data?.error ?? data?.message ?? `HTTP ${res.status}`;
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

export function executeHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (EXECUTE_SERIAL_TOKEN && String(EXECUTE_SERIAL_TOKEN).trim() !== "") {
    headers["X-Execute-Token"] = String(EXECUTE_SERIAL_TOKEN);
  }
  return headers;
}

export function apiBaseUrl() {
  return BASE_URL;
}
