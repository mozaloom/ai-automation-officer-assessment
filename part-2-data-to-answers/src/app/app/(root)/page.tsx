"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Spinner from "@/components/ui/Spinner";
import { detectLocale, LOCALE_STORAGE_KEY, withLocale } from "@/lib/i18n/config";

/** "/" opens in the visitor's language: their saved choice, else the browser's language list, else English. */
export default function Root() {
  const router = useRouter();
  useEffect(() => {
    let saved: string | null = null;
    try { saved = window.localStorage.getItem(LOCALE_STORAGE_KEY); } catch { /* storage blocked: fall back to the browser language */ }
    router.replace(withLocale(detectLocale(saved, navigator.languages), "/dashboard/"));
  }, [router]);
  return (
    <>
      <Spinner />
      <noscript><p><Link href="/en/dashboard/">English</Link> · <Link href="/ar/dashboard/" lang="ar">العربية</Link></p></noscript>
    </>
  );
}
