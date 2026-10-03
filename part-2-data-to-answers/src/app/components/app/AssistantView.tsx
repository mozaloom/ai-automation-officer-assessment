"use client";

import { useI18n } from "@/lib/i18n/I18nProvider";
import ChatPanel from "./ChatPanel";

export default function AssistantView() {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-text-dark">{t.assistant.title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-gray">{t.assistant.subtitle}</p>
      </header>
      <ChatPanel />
    </div>
  );
}
