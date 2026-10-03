import { beforeEach, describe, expect, it, vi } from "vitest";
import { configureApi } from "@/lib/api/client";
import { parseSse, streamAnswer } from "@/lib/api/stream";
import { ApiError, type StreamEvent } from "@/lib/api/types";

const frame = (event: object) => `data: ${JSON.stringify(event)}\n\n`;
const encoder = new TextEncoder();

/** A Response whose body arrives in the given byte chunks, like a network stream. */
function streamed(chunks: Uint8Array[], init: ResponseInit = { status: 200, headers: { "Content-Type": "text/event-stream" } }) {
  return new Response(new ReadableStream({ start(controller) { chunks.forEach((c) => controller.enqueue(c)); controller.close(); } }), init);
}

describe("parseSse", () => {
  it("returns complete events and keeps the unfinished tail", () => {
    const { events, rest } = parseSse(`${frame({ type: "start", session_id: "s" })}${frame({ type: "delta", text: "ab" })}data: {"type":"del`);
    expect(events).toEqual([{ type: "start", session_id: "s" }, { type: "delta", text: "ab" }]);
    expect(rest).toBe('data: {"type":"del');
  });
  it("accepts CRLF line endings, comments and a missing space after the colon", () => {
    const { events } = parseSse(`: keep-alive\r\n\r\ndata:{"type":"reset"}\r\n\r\n`);
    expect(events).toEqual([{ type: "reset" }]);
  });
  it("skips malformed frames instead of failing the whole answer", () => {
    expect(parseSse(`data: {oops}\n\n${frame({ type: "reset" })}`).events).toEqual([{ type: "reset" }]);
  });
});

describe("streamAnswer", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    configureApi({ getToken: () => "tok", refresh: async () => null, onUnauthorized: () => {} });
  });
  const run = (onEvent: (e: StreamEvent) => void = () => {}, signal?: AbortSignal) => streamAnswer({ prompt: "tahini?", sessionId: "s".repeat(36), locale: "ar", signal, onEvent });
  const done = { type: "done", answer: "ok", records: [], queries: [], record_count: 0, data_as_of: "2026-08-25", session_id: "s", grounded: true };

  it("posts the question with the Bearer token, session header and language", async () => {
    fetchMock.mockResolvedValue(streamed([encoder.encode(frame(done))]));
    await run();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/ask");
    expect(init).toMatchObject({ method: "POST", credentials: "omit" });
    expect(init.headers).toMatchObject({ Authorization: "Bearer tok", Accept: "text/event-stream", "Content-Type": "application/json", "x-session-id": "s".repeat(36) });
    expect(JSON.parse(init.body)).toEqual({ prompt: "tahini?", locale: "ar" });
  });

  it("delivers events in order as chunks arrive, even when a chunk splits an event or a multi-byte character", async () => {
    const bytes = encoder.encode(frame({ type: "delta", text: "طحينة" }) + frame({ type: "delta", text: " متوفرة" }) + frame(done));
    const cut = bytes.indexOf(0xd8, 20) + 1; // inside the first Arabic letter's two bytes
    fetchMock.mockResolvedValue(streamed([bytes.slice(0, cut), bytes.slice(cut, cut + 7), bytes.slice(cut + 7)]));
    const seen: StreamEvent[] = [];
    await run((e) => seen.push(e));
    expect(seen.map((e) => e.type)).toEqual(["delta", "delta", "done"]);
    expect(seen.filter((e): e is Extract<StreamEvent, { type: "delta" }> => e.type === "delta").map((e) => e.text).join("")).toBe("طحينة متوفرة");
  });

  it("handles a final event that has no trailing blank line", async () => {
    fetchMock.mockResolvedValue(streamed([encoder.encode(`data: ${JSON.stringify(done)}`)]));
    const seen: StreamEvent[] = [];
    await run((e) => seen.push(e));
    expect(seen.map((e) => e.type)).toEqual(["done"]);
  });

  it("turns an error event into an ApiError carrying its code", async () => {
    fetchMock.mockResolvedValue(streamed([encoder.encode(frame({ type: "error", code: "agent_error", message: "x" }))]));
    await expect(run()).rejects.toMatchObject({ code: "agent_error" });
  });

  it("reports a stream that ends before `done` as interrupted", async () => {
    fetchMock.mockResolvedValue(streamed([encoder.encode(frame({ type: "delta", text: "partial" }))]));
    const seen: StreamEvent[] = [];
    await expect(run((e) => seen.push(e))).rejects.toMatchObject({ code: "stream_interrupted" });
    expect(seen).toHaveLength(1); // what arrived is still delivered
  });

  it("maps HTTP failures (gateway errors) to ApiError", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ message: "Too Many Requests" }), { status: 429 }));
    const err = await run().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(429);
  });

  it("refreshes an expired token once and retries", async () => {
    configureApi({ getToken: () => "old", refresh: async () => "new" });
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 401 })).mockResolvedValueOnce(streamed([encoder.encode(frame(done))]));
    await run();
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer new");
  });

  it("passes the abort signal to fetch so Stop really cancels the request", async () => {
    const controller = new AbortController();
    fetchMock.mockImplementation((_url: string, init: RequestInit) => new Promise((_resolve, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))));
    const pending = run(() => {}, controller.signal);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
