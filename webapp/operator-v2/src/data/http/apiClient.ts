const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

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

async function readJson(response: Response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { ham: text };
  }
}

function resolveApiErrorMessage(data: unknown, status: number) {
  if (typeof data === "object" && data !== null) {
    const candidate = data as Record<string, unknown>;
    const detail = candidate.detail ?? candidate.error ?? candidate.message;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }

  return `HTTP ${status}`;
}

export async function postJson<T>(
  path: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers
    },
    body: JSON.stringify(body)
  });

  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(resolveApiErrorMessage(data, response.status), response.status, data);
  }

  return data as T;
}

export async function postForm<T>(
  path: string,
  body: FormData,
  headers: Record<string, string> = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body
  });

  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(resolveApiErrorMessage(data, response.status), response.status, data);
  }

  return data as T;
}

export function apiBaseUrl() {
  return API_BASE;
}
