import type { Viewport } from "next";
import { fontVariables } from "@/lib/fonts";
import { directionOf, type Locale } from "@/lib/i18n/config";
import { MESSAGES } from "@/lib/i18n/messages";
import "@/app/globals.css";

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#FFFFFF", colorScheme: "light" };

/** The <html> document for one language: `lang` and `dir` are set here so the page is right before any script runs. */
export default function RootDocument({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  return (
    <html lang={locale} dir={directionOf(locale)} className={fontVariables}>
      <body className="font-sans antialiased">
        <a href="#main" className="skip-nav">{MESSAGES[locale].app.skipToContent}</a>
        {children}
      </body>
    </html>
  );
}
