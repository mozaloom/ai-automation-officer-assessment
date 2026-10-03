"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, RotateCcw, SendHorizonal, Sparkles, User } from "lucide-react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { askAssistant } from "@/lib/api/availability";
import type { PosRecord } from "@/lib/api/types";
import AnswerMarkdown from "./AnswerMarkdown";
import RecordsTable from "./RecordsTable";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  records?: PosRecord[];
  total?: number;
  asOf?: string;
  grounded?: boolean;
  failed?: boolean;
}

export const SAMPLE_QUESTIONS = [
  "Where can I buy Olive Oil Extra Virgin in Amman?",
  "Which shops in Abdoun have Instant Coffee?",
  "Where can I find 3 L Sunflower Cooking Oil?",
  "Which stores have low stock of Olive Oil?",
  "Where can I buy tea?",
  "Does Sameh Mall Abdoun have Basmati Rice?",
];

const newSessionId = () => crypto.randomUUID(); // 36 characters, above the 33 the runtime requires

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [sessionId, setSessionId] = useState(newSessionId);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [messages, pending]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || pending) return;
    setInput("");
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", text: question }]);
    setPending(true);
    try {
      const res = await askAssistant(question, sessionId);
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", text: res.answer, records: res.records, total: res.record_count, asOf: res.data_as_of, grounded: res.grounded }]);
    } catch (err) {
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", failed: true, text: err instanceof Error ? err.message : "Something went wrong. Please try again." }]);
    } finally {
      setPending(false);
    }
  }

  const reset = () => { setMessages([]); setSessionId(newSessionId()); setInput(""); };

  return (
    <Card padding="none" className="flex min-h-[28rem] flex-col">
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-dark"><Sparkles className="h-4 w-4 text-brand-blue" aria-hidden="true" />Availability assistant</div>
        <Button variant="pill-outline" size="sm" onClick={reset} disabled={!messages.length && !pending}><RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />New chat</Button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5" role="log" aria-live="polite" aria-label="Conversation" style={{ maxHeight: "60vh" }}>
        {messages.length === 0 && (
          <div className="py-4">
            <div className="flex items-start gap-3">
              <Avatar assistant />
              <div className="max-w-xl rounded-2xl rounded-bl-sm border border-gray-100 bg-white px-4 py-3 text-sm text-text-dark shadow-sm">
                Ask where a product can be bought, in which city, area or store, and in what state. I answer only from the latest recorded POS data.
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2" aria-label="Sample questions">
              {SAMPLE_QUESTIONS.map((q) => (
                <button key={q} type="button" onClick={() => send(q)} className="rounded-full border border-black/15 px-4 py-2 text-left text-sm text-text-dark transition-colors hover:bg-black/[0.04]">{q}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`flex items-start gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
            <Avatar assistant={m.role === "assistant"} />
            <div className={m.role === "user" ? "max-w-xl" : "min-w-0 flex-1"}>
              <div className={m.role === "user"
                ? "rounded-2xl rounded-br-sm bg-brand-blue px-4 py-3 text-sm text-white"
                : `rounded-2xl rounded-bl-sm border px-4 py-3 text-sm text-text-dark shadow-sm ${m.failed ? "border-red-100 bg-red-50 text-red-700" : "border-gray-100 bg-white"}`}>
                {m.failed && <AlertTriangle className="mb-1 h-4 w-4" aria-hidden="true" />}
                {m.role === "assistant" && !m.failed ? <AnswerMarkdown>{m.text}</AnswerMarkdown> : m.text}
                {m.grounded === false && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">This summary could not be fully verified, so please rely on the records below.</p>}
              </div>
              {m.role === "assistant" && m.records && m.records.length > 0 && <RecordsTable records={m.records} total={m.total ?? m.records.length} asOf={m.asOf ?? ""} />}
            </div>
          </div>
        ))}

        {pending && (
          <div className="flex items-start gap-3" role="status" aria-label="The assistant is typing">
            <Avatar assistant />
            <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-gray-100 bg-white px-4 py-4 shadow-sm">
              {[0, 150, 300].map((d) => <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-brand-purple/60" style={{ animationDelay: `${d}ms` }} />)}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); void send(input); }} className="border-t border-gray-100 p-4">
        <div className="flex items-center gap-3">
          <label htmlFor="question" className="sr-only">Your question</label>
          <input id="question" value={input} onChange={(e) => setInput(e.target.value)} maxLength={500} placeholder="Ask about product availability" autoComplete="off"
            className="h-12 flex-1 rounded-xl border border-gray-200 bg-white px-4 text-sm text-text-dark shadow-sm outline-none transition placeholder:text-text-light focus:border-brand-blue/40 focus:ring-2 focus:ring-brand-blue/30" />
          <Button type="submit" variant="pill" loading={pending} disabled={!input.trim()} aria-label="Send question" className="h-12"><SendHorizonal className="h-4 w-4" aria-hidden="true" /><span className="hidden sm:inline">Send</span></Button>
        </div>
        <p className="mt-2 text-xs text-text-gray">Availability is the latest recorded POS data, not a live inventory feed.</p>
      </form>
    </Card>
  );
}

function Avatar({ assistant }: { assistant?: boolean }) {
  return (
    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${assistant ? "bg-gradient-to-br from-brand-blue/15 to-brand-cyan/20 text-brand-blue" : "bg-gray-100 text-text-gray"}`} aria-hidden="true">
      {assistant ? <Sparkles className="h-4 w-4" /> : <User className="h-4 w-4" />}
    </span>
  );
}
