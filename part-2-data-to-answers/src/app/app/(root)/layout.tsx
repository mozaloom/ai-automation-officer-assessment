import type { Metadata } from "next";
import RootDocument from "@/components/RootDocument";
import { DEFAULT_LOCALE } from "@/lib/i18n/config";

export { viewport } from "@/components/RootDocument";
export const metadata: Metadata = { title: "XPAND Availability" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <RootDocument locale={DEFAULT_LOCALE}>{children}</RootDocument>;
}
