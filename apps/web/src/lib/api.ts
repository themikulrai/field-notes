// REST client for the Field Notes API. Reads VITE_API_URL + localStorage key.
// One function per endpoint, matching CellRead / ProjectRead shapes.

import type {
  Cell,
  CellCreate,
  CellUpdate,
  Project,
  ProjectCreate,
  ProjectUpdate,
  ReorderRequest,
  VerdictSet,
} from "./types";

const STORAGE_KEY = "field-notes-key";

function envApiUrl(): string {
  const e = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
  const url = e?.VITE_API_URL;
  // Production build sets VITE_API_URL="" so we fall through to the current
  // origin — the API serves the SPA from the same host on Fly.io. In dev we
  // hit localhost:8000 by default so `npm run dev` Just Works.
  if (url && url.length > 0) return url;
  if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
  return "http://localhost:8000";
}
function envDefaultKey(): string | undefined {
  const e = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
  return e?.VITE_DEFAULT_KEY;
}

export function getApiKey(): string | null {
  // localStorage may be unavailable (jsdom without setup); guard.
  try {
    const v = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    if (v && v.length > 0) return v;
  } catch {
    /* ignore */
  }
  return envDefaultKey() ?? null;
}

export function setApiKey(k: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, k);
  } catch {
    /* ignore */
  }
}

export function clearApiKey(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | undefined>;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const base = envApiUrl().replace(/\/$/, "");
  const key = getApiKey();
  const qs = opts.query
    ? "?" +
      Object.entries(opts.query)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v as string)}`)
        .join("&")
    : "";
  const url = `${base}${path}${qs}`;
  const headers: Record<string, string> = {};
  if (key) headers["X-Field-Notes-Key"] = key;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(url, {
    method: opts.method || "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    const detail =
      parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail, parsed);
  }
  return parsed as T;
}

// Projects -----------------------------------------------------------------
export function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}
export function createProject(body: ProjectCreate): Promise<Project> {
  return request<Project>("/projects", { method: "POST", body });
}
export function getProject(pid: string): Promise<Project> {
  return request<Project>(`/projects/${pid}`);
}
export function updateProject(pid: string, body: ProjectUpdate): Promise<Project> {
  return request<Project>(`/projects/${pid}`, { method: "PATCH", body });
}
export function deleteProject(pid: string): Promise<void> {
  return request<void>(`/projects/${pid}`, { method: "DELETE" });
}

// Cells --------------------------------------------------------------------
export function listCells(pid: string): Promise<Cell[]> {
  return request<Cell[]>(`/projects/${pid}/cells`);
}
export function createCell(pid: string, body: CellCreate): Promise<Cell> {
  return request<Cell>(`/projects/${pid}/cells`, { method: "POST", body });
}
export function getCell(cid: string): Promise<Cell> {
  return request<Cell>(`/cells/${cid}`);
}
export function updateCell(cid: string, body: CellUpdate): Promise<Cell> {
  return request<Cell>(`/cells/${cid}`, { method: "PATCH", body });
}
export function deleteCell(cid: string): Promise<void> {
  return request<void>(`/cells/${cid}`, { method: "DELETE" });
}
export function reorderCell(cid: string, body: ReorderRequest): Promise<Cell> {
  return request<Cell>(`/cells/${cid}/reorder`, { method: "POST", body });
}

// Verdicts + lock ----------------------------------------------------------
export function setVerdict(cid: string, body: VerdictSet): Promise<Cell> {
  return request<Cell>(`/cells/${cid}/verdict`, { method: "POST", body });
}
export function clearVerdict(cid: string): Promise<Cell> {
  // body: null per API contract — fetch can't send literal `null` as JSON unless
  // we explicitly stringify it. Use an empty body with no Content-Type by
  // sending body: undefined and method POST; FastAPI treats missing body as null.
  return request<Cell>(`/cells/${cid}/verdict`, { method: "POST" });
}
export function lockCell(cid: string): Promise<Cell> {
  return request<Cell>(`/cells/${cid}/lock`, { method: "POST" });
}
export function unlockCell(cid: string): Promise<Cell> {
  return request<Cell>(`/cells/${cid}/unlock`, { method: "POST" });
}

// Helpers exposed for tests / SSE ------------------------------------------
export function apiBaseUrl(): string {
  return envApiUrl().replace(/\/$/, "");
}
