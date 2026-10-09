import type { Metadata } from "next";
import InboxView from "@/components/inbox/InboxView";
import { isLocale } from "@/lib/i18n/config";
import { MESSAGES } from "@/lib/i18n/messages";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: MESSAGES[locale].inbox.nav.inbox } : {};
}

export default function Page() {
  return <InboxView />;
}
