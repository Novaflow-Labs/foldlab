// HTTP + SSE client (FROZEN CONTRACT). Phase-1 agents call these helpers; do not
// hand-roll fetch elsewhere. Dev requests go to /api (proxied to the backend).

import type { ChatRequest, Directive, JobRef } from "../types";

const BASE = "/api";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return fetch(`${BASE}${path}`).then((r) => handle<T>(r));
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

export function apiDelete(path: string): Promise<void> {
  return fetch(`${BASE}${path}`, { method: "DELETE" }).then((r) => handle<void>(r));
}

/** URL the Mol* viewer loads structure bytes from. */
export function structureUrl(jobId: number): string {
  return `${BASE}/jobs/${jobId}/structure`;
}

export interface ChatStreamHandlers {
  onText?: (delta: string) => void;
  onDirective?: (d: Directive) => void;
  onToolResult?: (payload: Record<string, unknown>) => void;
  onJob?: (job: JobRef) => void;
  onDone?: (payload: Record<string, unknown>) => void;
  onError?: (message: string) => void;
}

/**
 * POST-based SSE consumer for /api/chat (native EventSource is GET-only).
 * Returns an AbortController — call .abort() to cancel the stream.
 */
export function streamChat(req: ChatRequest, h: ChatStreamHandlers): AbortController {
  const controller = new AbortController();
  void (async () => {
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        h.onError?.(`chat failed: ${res.status}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const blocks = buf.split("\n\n");
        buf = blocks.pop() ?? "";
        for (const block of blocks) dispatch(block, h);
      }
      if (buf.trim()) dispatch(buf, h);
    } catch (e) {
      const err = e as { name?: string; message?: string };
      if (err?.name !== "AbortError") h.onError?.(String(err?.message ?? e));
    }
  })();
  return controller;
}

function dispatch(block: string, h: ChatStreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    payload = { raw: dataLines.join("\n") };
  }
  switch (event) {
    case "text":
      h.onText?.(String(payload.delta ?? ""));
      break;
    case "directive":
      h.onDirective?.(payload as unknown as Directive);
      break;
    case "tool_result":
      h.onToolResult?.(payload);
      break;
    case "job":
      h.onJob?.(payload as unknown as JobRef);
      break;
    case "done":
      h.onDone?.(payload);
      break;
    case "error":
      h.onError?.(String(payload.message ?? "error"));
      break;
  }
}
