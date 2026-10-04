"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "@/lib/auth/SessionProvider";
import { I18nProvider } from "@/lib/i18n/I18nProvider";
import { LOCALE_STORAGE_KEY, type Locale } from "@/lib/i18n/config";

export default function Providers({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } }));
  useEffect(() => {
    try { window.localStorage.setItem(LOCALE_STORAGE_KEY, locale); } catch { /* storage blocked: the URL still carries the language */ }
  }, [locale]);
  return (
    <I18nProvider locale={locale}>
      <QueryClientProvider client={client}><SessionProvider>{children}</SessionProvider></QueryClientProvider>
    </I18nProvider>
  );
}
