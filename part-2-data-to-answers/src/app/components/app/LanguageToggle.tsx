"use client";

import { usePathname } from "next/navigation";
import { switchLocalePath, type Locale } from "@/lib/i18n/config";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Switches the page to the other language and keeps the path, query and hash. A full navigation, so `lang` and `dir` reset cleanly. */
export default function LanguageToggle({ className = "" }: { className?: string }) {
  const { locale, t } = useI18n();
  const pathname = usePathname();
  const target: Locale = locale === "ar" ? "en" : "ar";
  const href = switchLocalePath(pathname, target);
  return (
    <a
      href={href}
      lang={target}
      hrefLang={target}
      aria-label={t.nav.switchLanguageLabel}
      onClick={(event) => {
        event.preventDefault();
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- a full reload on purpose: <html lang/dir> and fonts reset cleanly
        window.location.assign(`${href}${window.location.search}${window.location.hash}`);
      }}
      className={`${target === "ar" ? "font-arabic" : ""} inline-flex h-9 items-center rounded-full border border-black/15 px-4 text-sm font-medium text-text-dark transition-colors hover:bg-black/[0.04] ${className}`}
    >
      {t.nav.switchLanguage}
    </a>
  );
}
