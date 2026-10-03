import type { Metadata } from "next";
import { notFound } from "next/navigation";
import RootDocument from "@/components/RootDocument";
import Providers from "@/lib/Providers";
import { isLocale, LOCALES } from "@/lib/i18n/config";
import { MESSAGES } from "@/lib/i18n/messages";

export { viewport } from "@/components/RootDocument";
export const dynamicParams = false; // only /en and /ar exist (static export)

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const { app } = MESSAGES[locale];
  return { title: { default: app.name, template: `%s | ${app.name}` }, description: app.description };
}

export default async function LocaleLayout({ children, params }: { children: React.ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return (
    <RootDocument locale={locale}>
      <Providers locale={locale}>{children}</Providers>
    </RootDocument>
  );
}
