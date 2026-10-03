import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "@/lib/i18n/I18nProvider";
import type { Locale } from "@/lib/i18n/config";

/** Renders inside the i18n provider for one language (English unless stated). */
export const renderI18n = (ui: ReactElement, locale: Locale = "en") => render(<I18nProvider locale={locale}>{ui}</I18nProvider>);
