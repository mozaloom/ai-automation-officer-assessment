"use client";

import { useI18n } from "@/lib/i18n/I18nProvider";

/** Shown instead of the bare framework error page if a screen fails while rendering. */
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  const { t, href } = useI18n();
  return (
    <main id="main" className="flex min-h-dvh flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-xl font-bold text-text-dark">{t.crash.title}</h1>
      <p className="max-w-sm text-sm text-text-gray">{t.crash.body}</p>
      <div className="mt-2 flex gap-3">
        <button type="button" onClick={reset} className="h-11 rounded-full bg-black px-6 text-sm font-medium text-white transition-transform active:scale-[0.97]">{t.crash.reload}</button>
        <a href={href("/dashboard/")} className="inline-flex h-11 items-center rounded-full border border-black/15 px-6 text-sm font-medium text-text-dark">{t.crash.back}</a>
      </div>
    </main>
  );
}
