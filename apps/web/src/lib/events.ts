// EventSource wrapper for /events. Now uses short-lived HMAC tokens minted at
// POST /sse-token so the API key never appears in URL/router logs. Refreshes
// the token ~10s before expiry and reconnects with the new one. Reconnects on
// error with exponential backoff.

import { apiBaseUrl, getApiKey } from "./api";
import type { EventEnvelope } from "./types";

type Listener = (env: EventEnvelope) => void;

export interface EventStream {
  close(): void;
}

const MAX_BACKOFF_MS = 30_000;
const REFRESH_LEAD_MS = 10_000;

interface SseTokenResponse {
  token: string;
  expires_at: string;
  ttl_seconds: number;
}

export async function fetchSseToken(): Promise<SseTokenResponse> {
  const key = getApiKey() || "";
  const res = await fetch(`${apiBaseUrl()}/sse-token`, {
    method: "POST",
    headers: { "X-Field-Notes-Key": key },
  });
  if (!res.ok) throw new Error(`sse-token: ${res.status}`);
  return (await res.json()) as SseTokenResponse;
}

export function openEventStream(
  projectId: string | null,
  onEvent: Listener,
  onError?: (err: unknown) => void,
): EventStream {
  let closed = false;
  let es: EventSource | null = null;
  let backoff = 1000;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let refreshTimer: ReturnType<typeof setTimeout> | null = null;

  const buildUrl = (token: string) => {
    const params = new URLSearchParams({ token });
    if (projectId) params.set("project", projectId);
    return `${apiBaseUrl()}/events?${params.toString()}`;
  };

  const handleMessage = (raw: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(raw.data) as EventEnvelope);
    } catch (e) {
      onError?.(e);
    }
  };

  const scheduleRefresh = (ttlSeconds: number) => {
    if (refreshTimer) clearTimeout(refreshTimer);
    const delay = Math.max(1000, ttlSeconds * 1000 - REFRESH_LEAD_MS);
    refreshTimer = setTimeout(() => {
      if (closed) return;
      // Force reconnect with a fresh token.
      if (es) {
        es.close();
        es = null;
      }
      void connect();
    }, delay);
  };

  const connect = async () => {
    if (closed) return;
    if (typeof EventSource === "undefined") {
      onError?.(new Error("EventSource unavailable"));
      return;
    }
    let tok: SseTokenResponse;
    try {
      tok = await fetchSseToken();
    } catch (e) {
      onError?.(e);
      if (closed) return;
      reconnectTimer = setTimeout(() => void connect(), backoff);
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
      return;
    }
    if (closed) return;
    es = new EventSource(buildUrl(tok.token));
    es.onopen = () => {
      backoff = 1000;
    };
    es.onmessage = handleMessage;
    es.onerror = (e) => {
      onError?.(e);
      if (es) {
        es.close();
        es = null;
      }
      if (closed) return;
      reconnectTimer = setTimeout(() => void connect(), backoff);
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    };
    scheduleRefresh(tok.ttl_seconds);
  };

  void connect();

  return {
    close() {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (refreshTimer) clearTimeout(refreshTimer);
      if (es) {
        es.close();
        es = null;
      }
    },
  };
}
