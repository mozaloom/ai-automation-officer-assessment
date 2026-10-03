import type { Metadata } from "next";
import LoginView from "@/components/auth/LoginView";
import { isLocale } from "@/lib/i18n/config";
import { MESSAGES } from "@/lib/i18n/messages";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: MESSAGES[locale].login.title } : {};
}

export default function LoginPage() {
  return <LoginView />;
}
