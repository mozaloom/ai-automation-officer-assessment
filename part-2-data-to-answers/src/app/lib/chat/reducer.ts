import type { PosRecord, StreamEvent } from "@/lib/api/types";

export type Phase = "searching" | "writing" | "done" | "stopped" | "error";

export interface UserMessage { id: string; role: "user"; text: string }
export interface AssistantMessage {
  id: string;
  role: "assistant";
  question: string; // kept so a failed answer can be retried
  text: string;
  phase: Phase;
  records: PosRecord[];
  total: number;
  asOf: string;
  grounded?: boolean;
  error?: string;
}
export type ChatMessage = UserMessage | AssistantMessage;

export type ChatAction =
  | { type: "ask"; userId: string; assistantId: string; text: string }
  | { type: "retry"; failedId: string; assistantId: string }
  | { type: "event"; id: string; event: StreamEvent }
  | { type: "fail"; id: string; message: string }
  | { type: "stop"; id: string }
  | { type: "reset" };

const pending = (id: string, question: string): AssistantMessage => ({ id, role: "assistant", question, text: "", phase: "searching", records: [], total: 0, asOf: "" });

function applyEvent(m: AssistantMessage, event: StreamEvent): AssistantMessage {
  switch (event.type) {
    case "start":
    case "status":
      return { ...m, phase: "searching" };
    case "records":
      return { ...m, records: event.records, total: event.record_count, asOf: event.data_as_of };
    case "delta":
      return { ...m, text: m.text + event.text, phase: "writing" };
    case "reset":
      return { ...m, text: "", phase: "searching" };
    case "replace":
      return { ...m, text: event.text };
    case "done":
      return { ...m, text: event.answer, records: event.records, total: event.record_count, asOf: event.data_as_of, grounded: event.grounded, phase: "done" };
    default:
      return m;
  }
}

/** Pure state machine for the conversation, so the streaming behaviour can be tested without a browser. */
export function chatReducer(state: ChatMessage[], action: ChatAction): ChatMessage[] {
  switch (action.type) {
    case "ask":
      return [...state, { id: action.userId, role: "user", text: action.text }, pending(action.assistantId, action.text)];
    case "retry": {
      const failed = state.find((m): m is AssistantMessage => m.id === action.failedId && m.role === "assistant");
      return failed ? state.map((m) => (m.id === action.failedId ? pending(action.assistantId, failed.question) : m)) : state;
    }
    case "event":
      return state.map((m) => (m.id === action.id && m.role === "assistant" ? applyEvent(m, action.event) : m));
    case "fail":
      return state.map((m) => (m.id === action.id && m.role === "assistant" ? { ...m, phase: "error", error: action.message } : m));
    case "stop":
      return state.map((m) => (m.id === action.id && m.role === "assistant" && m.phase !== "done" ? { ...m, phase: "stopped" } : m));
    case "reset":
      return [];
  }
}
