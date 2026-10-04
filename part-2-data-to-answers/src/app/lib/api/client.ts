import { API_BASE_URL } from "@/lib/config";
import { ApiError } from "./types";

type TokenGetter = () => string | null;
type Refresher = () => Promise<string | null>;

let tokenGetter: TokenGetter = () => null;
let onUnauthorized: () => void = () => {};
let refresher: Refresher = async () => null;

// Single-flight guard: concurrent 401s trigger one refresh.
let inflightRefresh: Promise<string | null> | null = null;
function refreshOnce(): Promise<string | null> {
  if (!inflightRefresh) inflightRefresh = refresher().finally(() => { inflightRefresh = null; });
  return inflightRefresh;
}

export function configureApi(opts: { getToken: TokenGetter; onUnauthorized?: () => void; refresh?: Refresher }) {
  tokenGetter = opts.getToken;
  if (opts.onUnauthorized) onUnauthorized = opts.onUnauthorized;
  if (opts.refresh) refresher = opts.refresh;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return `${API_BASE_URL}${path}${qs ? `?${qs}` : ""}`;
}

async function send(url: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", ...opts.headers };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`; // the Cognito ID token; API Gateway and the runtime both validate it
  return fetch(url, { method: opts.method ?? "GET", headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined, credentials: "omit", signal: opts.signal });
}

/** Authenticated request: adds the token and retries once with a refreshed token after a 401. Returns the raw Response. */
export async function authorizedRequest(path: string, opts: RequestOptions = {}): Promise<Response> {
  const url = buildUrl(path, opts.query);
  let res = await send(url, opts, tokenGetter());
  if (res.status === 401) {
    const fresh = await refreshOnce();
    if (fresh) res = await send(url, opts, fresh);
    if (res.status === 401) onUnauthorized();
  }
  return res;
}

/** Builds an ApiError from a failed response body (gateway errors and runtime errors have different shapes). */
export function apiErrorFrom(status: number, text: string): ApiError {
  let payload: unknown;
  try { payload = text ? JSON.parse(text) : undefined; } catch { payload = text; }
  const obj = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : null;
  const nested = obj && obj.error && typeof obj.error === "object" ? (obj.error as Record<string, unknown>) : null;
  const message = (nested && typeof nested.message === "string" && nested.message) || (obj && typeof obj.message === "string" && obj.message) || `Request failed with ${status}`;
  return new ApiError(status, message, payload, nested && typeof nested.code === "string" ? nested.code : undefined);
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await authorizedRequest(path, opts);
  const text = await res.text();
  if (!res.ok) throw apiErrorFrom(res.status, text);
  try { return (text ? JSON.parse(text) : undefined) as T; } catch { return text as unknown as T; }
}
