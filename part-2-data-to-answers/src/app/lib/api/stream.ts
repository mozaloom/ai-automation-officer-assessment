import { authorizedRequest, apiErrorFrom } from "./client";
import { ApiError, type StreamEvent } from "./types";

/** Splits the buffer into complete Server-Sent Events frames and parses their JSON `data:` lines. */
export function parseSse(buffer: string): { events: StreamEvent[]; rest: string } {
  const frames = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = frames.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const frame of frames) {
    const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).replace(/^ /, "")).join("\n");
    if (!data) continue;
    try { events.push(JSON.parse(data) as StreamEvent); } catch { /* ignore a malformed frame rather than lose the answer */ }
  }
  return { events, rest };
}

export interface StreamOptions {
  prompt: string;
  sessionId: string;
  locale: "en" | "ar";
  signal?: AbortSignal;
  onEvent: (event: StreamEvent) => void;
}

/**
 * Asks the assistant and reports each event as it arrives. Resolves after `done`; throws ApiError for HTTP errors,
 * an `error` event, or a stream that ended without finishing (code "stream_interrupted"). Aborting throws AbortError.
 */
export async function streamAnswer({ prompt, sessionId, locale, signal, onEvent }: StreamOptions): Promise<void> {
  const res = await authorizedRequest("/ask", { method: "POST", body: { prompt, locale }, headers: { Accept: "text/event-stream", "x-session-id": sessionId }, signal });
  if (!res.ok) throw apiErrorFrom(res.status, await res.text());
  if (!res.body) throw new ApiError(res.status, "The browser could not read the streamed answer.", undefined, "stream_unsupported");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let finished = false;
  const handle = (event: StreamEvent) => {
    onEvent(event);
    if (event.type === "done") finished = true;
    if (event.type === "error") throw new ApiError(200, event.message, event, event.code);
  };
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parsed = parseSse(done ? `${buffer}\n\n` : buffer);
    buffer = parsed.rest;
    parsed.events.forEach(handle);
    if (done) break;
  }
  if (!finished) throw new ApiError(200, "The answer was interrupted.", undefined, "stream_interrupted");
}
