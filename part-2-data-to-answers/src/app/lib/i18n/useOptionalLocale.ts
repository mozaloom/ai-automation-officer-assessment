"use client";

import { useContext } from "react";
import { DEFAULT_LOCALE, type Locale } from "./config";
import { I18nContext } from "./I18nProvider";

/** The current locale, or English where no provider exists (e.g. the "/" redirect page). */
export function useOptionalLocale(): Locale {
  return useContext(I18nContext)?.locale ?? DEFAULT_LOCALE;
}
