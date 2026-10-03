import { describe, expect, it } from "vitest";
import { chatReducer, type AssistantMessage, type ChatMessage } from "@/lib/chat/reducer";
import { askResponse, record } from "./fixtures";

const asked = (): ChatMessage[] => chatReducer([], { type: "ask", userId: "u1", assistantId: "a1", text: "tahini?" });
const assistant = (state: ChatMessage[]) => state.find((m): m is AssistantMessage => m.role === "assistant")!;
const event = (state: ChatMessage[], e: Parameters<typeof chatReducer>[1] extends infer A ? A extends { type: "event"; event: infer E } ? E : never : never) => chatReducer(state, { type: "event", id: "a1", event: e });

describe("chatReducer", () => {
  it("adds the question and a pending answer", () => {
    const state = asked();
    expect(state.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(assistant(state)).toMatchObject({ phase: "searching", text: "", question: "tahini?", records: [] });
  });

  it("shows the records as soon as they arrive, before any text", () => {
    const state = event(asked(), { type: "records", records: [record()], queries: [], record_count: 7, data_as_of: "2026-08-25" });
    expect(assistant(state)).toMatchObject({ records: [record()], total: 7, asOf: "2026-08-25", text: "", phase: "searching" });
  });

  it("appends text pieces in order", () => {
    let state = asked();
    for (const text of ["It is ", "in stock", "."]) state = event(state, { type: "delta", text });
    expect(assistant(state)).toMatchObject({ text: "It is in stock.", phase: "writing" });
  });

  it("clears the text on reset and swaps it on replace", () => {
    let state = event(event(asked(), { type: "delta", text: "draft" }), { type: "reset" });
    expect(assistant(state)).toMatchObject({ text: "", phase: "searching" });
    state = event(event(state, { type: "delta", text: "bad" }), { type: "replace", text: "safe fallback" });
    expect(assistant(state).text).toBe("safe fallback");
  });

  it("finishes with the verified answer, records and grounding flag", () => {
    const state = event(event(asked(), { type: "delta", text: "partial" }), { type: "done", ...askResponse({ answer: "final", grounded: false }) });
    expect(assistant(state)).toMatchObject({ text: "final", phase: "done", grounded: false, total: 1 });
  });

  it("fails and stops the right message only, keeping what was already shown", () => {
    const withText = event(asked(), { type: "delta", text: "half an answer" });
    expect(assistant(chatReducer(withText, { type: "fail", id: "a1", message: "boom" }))).toMatchObject({ phase: "error", error: "boom", text: "half an answer" });
    expect(assistant(chatReducer(withText, { type: "stop", id: "a1" }))).toMatchObject({ phase: "stopped", text: "half an answer" });
    expect(chatReducer(withText, { type: "stop", id: "other" })).toEqual(withText);
  });

  it("does not turn a finished answer into a stopped one", () => {
    const state = event(asked(), { type: "done", ...askResponse() });
    expect(assistant(chatReducer(state, { type: "stop", id: "a1" })).phase).toBe("done");
  });

  it("retries a failed answer in place with the same question", () => {
    const failed = chatReducer(asked(), { type: "fail", id: "a1", message: "boom" });
    const state = chatReducer(failed, { type: "retry", failedId: "a1", assistantId: "a2" });
    expect(state.map((m) => m.id)).toEqual(["u1", "a2"]);
    expect(assistant(state)).toMatchObject({ question: "tahini?", phase: "searching" });
  });

  it("ignores events for unknown messages and resets to empty", () => {
    const state = asked();
    expect(chatReducer(state, { type: "event", id: "nope", event: { type: "delta", text: "x" } })).toEqual(state);
    expect(chatReducer(state, { type: "reset" })).toEqual([]);
  });
});
