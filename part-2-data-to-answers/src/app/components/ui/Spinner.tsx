"use client";

import { MESSAGES } from "@/lib/i18n/messages";
import { useOptionalLocale } from "@/lib/i18n/useOptionalLocale";

/** Full-page loading state. Works outside <I18nProvider> too (the "/" redirect page). */
export default function Spinner() {
  const locale = useOptionalLocale();
  return (
    <div className="flex min-h-screen items-center justify-center" role="status" aria-label={MESSAGES[locale].app.loading}>
      <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-brand-blue/20 border-t-brand-blue" />
    </div>
  );
}
