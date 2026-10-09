"use client";

import { FlaskConical } from "lucide-react";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Shown whenever a part of the pipeline runs on a test adapter, so a demo can never be mistaken for the real integration. */
export default function ModeBanner({ outlook, clickup }: { outlook?: string; clickup?: string }) {
  const { t } = useI18n();
  const parts = [outlook === "sample" ? t.inbox.sampleMail : null, clickup === "sample" ? t.inbox.sampleClickUp : null].filter(Boolean) as string[];
  if (!parts.length) return null;
  return (
    <p role="note" className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
      <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{t.inbox.sampleBanner(parts.join(" + "))}</span>
    </p>
  );
}
