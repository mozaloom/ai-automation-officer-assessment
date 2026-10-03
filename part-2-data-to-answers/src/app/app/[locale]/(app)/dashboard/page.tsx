import type { Metadata } from "next";
import DashboardView from "@/components/app/DashboardView";
import { isLocale } from "@/lib/i18n/config";
import { MESSAGES } from "@/lib/i18n/messages";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: MESSAGES[locale].nav.dashboard } : {};
}

export default function DashboardPage() {
  return <DashboardView />;
}
