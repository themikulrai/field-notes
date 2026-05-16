// Tiny EventSource wrapper. Opens GET /events?key=...&project=... and emits
// parsed EventEnvelope objects. Reconnects with exponential backoff.

import { apiBaseUrl, getApiKey } from "./api";
import type { EventEnvelope } from "./types";

type Listener = (env: EventEnvelope) => void;

export interface EventStream {
  close(): void;
}

const MAX_BACKOFF_MS = 30_000;

export function openEventStream(
  projectId: string | null,
  onEvent: Listener,
  onError?: (err: unknown) => void,
): EventStream {
  let closed = false;
  let es: EventSource | null = null;
  let backoff = 1000;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const url = () => {
    const key = getApiKey() || "";
    const base = apiBaseUrl();
    const params = new URLSearchParams({ key });
    if (projectId) params.set("project", projectId);
    return `${base}/events?${params.toString()}`;
  };

  const handleMessage = (raw: MessageEvent<string>) => {
    try {
      const parsed = JSON.parse(raw.data) as EventEnvelope;
      onEvent(parsed);
    } catch (e) {
      onError?.(e);
    }
  };

  const connect = () => {
    if (closed) return;
    if (typeof EventSource === "undefined") {
      // jsdom or stripped runtime — fail soft.
      onError?.(new Error("EventSource unavailable"));
      return;
    }
    es = new EventSource(url());
    es.onopen = () => {
      backoff = 1000; // reset
    };
    es.onmessage = handleMessage;
    es.onerror = (e) => {
      onError?.(e);
      if (es) {
        es.close();
        es = null;
      }
      if (closed) return;
      reconnectTimer = setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    };
  };

  connect();

  return {
    close() {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (es) {
        es.close();
        es = null;
      }
    },
  };
}
