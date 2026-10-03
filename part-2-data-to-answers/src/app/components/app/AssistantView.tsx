"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n/I18nProvider";
import ChatPanel from "./ChatPanel";

export default function AssistantView() {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  // Full-screen focus mode: Escape leaves it, and the page behind does not scroll.
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setExpanded(false); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [expanded]);
  return (
    <div className="space-y-6">
      <header className={expanded ? "sr-only" : ""}>
        <h1 className="text-2xl font-bold tracking-tight text-text-dark">{t.assistant.title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-gray">{t.assistant.subtitle}</p>
      </header>
      <div className={expanded ? "fixed inset-0 z-50 bg-white" : ""}>
        <ChatPanel expanded={expanded} onToggleExpanded={() => setExpanded((v) => !v)} />
      </div>
    </div>
  );
}
