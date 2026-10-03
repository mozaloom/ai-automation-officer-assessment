"use client";

import Image from "next/image";
import Link from "next/link";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** XPAND wordmark (brand asset supplied by the team) with the product name underneath. */
export default function Brand({ size = "md", href }: { size?: "sm" | "md"; href?: string }) {
  const { t, href: localized } = useI18n();
  const height = size === "md" ? 34 : 26;
  return (
    <Link href={href ?? localized("/dashboard/")} aria-label={t.nav.homeLabel} className="inline-flex flex-col gap-1">
      <Image src="/logos/xpand-logo.svg" alt="XPAND" translate="no" width={Math.round(height * (614.91 / 141.9))} height={height} priority style={{ height, width: "auto" }} />
      <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-gray">{t.app.brandSub}</span>
    </Link>
  );
}
