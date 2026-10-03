"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { AlertTriangle, ArrowUp, RotateCcw, Square } from "lucide-react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { describeError } from "@/lib/api/errors";
import { streamAnswer } from "@/lib/api/stream";
import type { StreamEvent } from "@/lib/api/types";
import { chatReducer, type AssistantMessage } from "@/lib/chat/reducer";
import { useI18n } from "@/lib/i18n/I18nProvider";
import AnswerMarkdown from "./AnswerMarkdown";
import RecordsTable from "./RecordsTable";

const newId = () => crypto.randomUUID(); // 36 characters: also valid as the runtime session id (it requires at least 33)
const MAX_LENGTH = 500;

export default function ChatPanel() {
  const { t, locale } = useI18n();
  const [messages, dispatch] = useReducer(chatReducer, []);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(newId);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const queue = useRef<{ id: string; event: StreamEvent }[]>([]);
  const frame = useRef<number | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);
  const streaming = streamingId !== null;

  // Text arrives in small pieces; render at most once per animation frame instead of once per piece.
  const flush = useCallback(() => {
    if (frame.current !== null) { cancelAnimationFrame(frame.current); frame.current = null; }
    for (const item of queue.current.splice(0)) dispatch({ type: "event", ...item });
  }, []);
  const enqueue = useCallback((id: string, event: StreamEvent) => {
    queue.current.push({ id, event });
    if (event.type === "done" || event.type === "replace") flush();
    else if (frame.current === null) frame.current = requestAnimationFrame(() => { frame.current = null; flush(); });
  }, [flush]);

  useEffect(() => () => { abort.current?.abort(); if (frame.current !== null) cancelAnimationFrame(frame.current); }, []);
  // A new message scrolls into view from its top, so a long records table never hides the start of the answer.
  const count = messages.length;
  useEffect(() => { logRef.current?.querySelector("[data-last]")?.scrollIntoView?.({ block: "start" }); }, [count]);

  const run = useCallback(async (assistantId: string, question: string, session: string) => {
    const controller = new AbortController();
    abort.current = controller;
    setStreamingId(assistantId);
    try {
      await streamAnswer({ prompt: question, sessionId: session, locale, signal: controller.signal, onEvent: (event) => enqueue(assistantId, event) });
      flush();
    } catch (err) {
      flush();
      if (err instanceof DOMException && err.name === "AbortError") dispatch({ type: "stop", id: assistantId });
      else dispatch({ type: "fail", id: assistantId, message: describeError(err, t) });
    } finally {
      abort.current = null;
      setStreamingId(null);
    }
  }, [enqueue, flush, locale, t]);

  const send = useCallback((text: string) => {
    const question = text.trim();
    if (!question || streaming) return;
    const assistantId = newId();
    setInput("");
    if (boxRef.current) boxRef.current.style.height = "";
    dispatch({ type: "ask", userId: newId(), assistantId, text: question });
    void run(assistantId, question, sessionId);
  }, [run, sessionId, streaming]);

  const retry = (failed: AssistantMessage) => {
    if (streaming) return;
    const assistantId = newId();
    dispatch({ type: "retry", failedId: failed.id, assistantId });
    void run(assistantId, failed.question, sessionId);
  };

  const reset = () => { abort.current?.abort(); dispatch({ type: "reset" }); setSessionId(newId()); setInput(""); };

  const last = messages[messages.length - 1];
  const announcement = last?.role === "assistant"
    ? last.phase === "searching" ? t.assistant.searching : last.phase === "done" ? t.assistant.done : last.phase === "stopped" ? t.assistant.stopped : last.phase === "error" ? last.error ?? "" : ""
    : "";

  return (
    <Card padding="none" className="flex min-h-[28rem] flex-col">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="text-sm font-semibold text-text-dark">{t.assistant.title}</h2>
        <Button variant="ghost" size="sm" onClick={reset} disabled={!messages.length}><RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />{t.assistant.newChat}</Button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto px-4 py-5 sm:px-6" ref={logRef} role="log" aria-live="off" aria-label={t.assistant.conversation} aria-busy={streaming} style={{ maxHeight: "62dvh" }}>
        {messages.length === 0 && (
          <div>
            <p className="max-w-xl text-sm leading-relaxed text-text-gray">{t.assistant.intro}</p>
            <ul className="mt-4 divide-y divide-line border-y border-line" aria-label={t.assistant.samplesLabel}>
              {t.assistant.samples.map((q) => (
                <li key={q}><button type="button" onClick={() => send(q)} className="w-full py-2.5 text-start text-sm text-text-dark transition-colors hover:text-brand-blue">{q}</button></li>
              ))}
            </ul>
          </div>
        )}

        {messages.map((m, index) => m.role === "user" ? (
          <div key={m.id} data-last={index === messages.length - 1 || undefined} className="enter flex justify-end">
            <p className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-wash px-3.5 py-2.5 text-sm text-text-dark"><span className="sr-only">{t.assistant.you}: </span>{m.text}</p>
          </div>
        ) : (
          <article key={m.id} data-last={index === messages.length - 1 || undefined} className="enter min-w-0 text-sm text-text-dark">
            <h3 className="sr-only">{t.assistant.assistantName}</h3>
            {m.phase === "searching" && !m.text && <p className="text-text-gray motion-safe:animate-pulse">{t.assistant.searching}</p>}
            {m.phase === "error" ? (
              <div className="flex flex-wrap items-center gap-3 rounded-md border border-red-100 bg-red-50 px-3 py-2.5 text-red-700">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1">{m.error}</span>
                <Button variant="outline" size="sm" onClick={() => retry(m)} disabled={streaming}>{t.assistant.retry}</Button>
              </div>
            ) : (
              <>
                {m.text && <div className="max-w-prose leading-relaxed"><AnswerMarkdown>{m.text}</AnswerMarkdown></div>}
                {m.phase === "stopped" && <p className="mt-1 text-xs text-text-gray">{t.assistant.stopped}</p>}
                {m.grounded === false && <p className="mt-2 max-w-prose rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">{t.assistant.unverified}</p>}
                {m.records.length > 0 && <RecordsTable records={m.records} total={m.total || m.records.length} asOf={m.asOf} />}
              </>
            )}
          </article>
        ))}
      </div>

      <div className="sr-only" role="status" aria-live="polite">{announcement}</div>

      <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="border-t border-line p-3 sm:p-4">
        <div className="flex items-end gap-2">
          <label htmlFor="question" className="sr-only">{t.assistant.question}</label>
          <textarea id="question" ref={boxRef} rows={1} value={input} maxLength={MAX_LENGTH} enterKeyHint="send" autoComplete="off" placeholder={t.assistant.placeholder}
            onChange={(e) => setInput(e.target.value)}
            onInput={(e) => { const el = e.currentTarget; el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 144)}px`; }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(input); } }}
            className="max-h-36 min-h-11 flex-1 resize-none rounded-md border border-[#d0d5dd] bg-white px-3.5 py-2.5 text-sm leading-6 text-text-dark placeholder:text-text-light outline-none transition-colors hover:border-[#9aa3d6] focus-visible:border-brand-blue focus-visible:ring-4 focus-visible:ring-brand-blue/15" />
          {streaming ? (
            <Button variant="outline" onClick={() => abort.current?.abort()} className="shrink-0"><Square className="h-3.5 w-3.5 fill-current" aria-hidden="true" />{t.assistant.stop}</Button>
          ) : (
            <Button type="submit" disabled={!input.trim()} aria-label={t.assistant.send} className="shrink-0"><ArrowUp className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">{t.assistant.send}</span></Button>
          )}
        </div>
        <p className="mt-2 text-xs text-text-gray">{t.assistant.footnote}</p>
      </form>
    </Card>
  );
}
