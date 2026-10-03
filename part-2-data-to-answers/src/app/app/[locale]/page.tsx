"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Spinner from "@/components/ui/Spinner";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function LocaleHome() {
  const router = useRouter();
  const { href } = useI18n();
  useEffect(() => { router.replace(href("/dashboard/")); }, [router, href]);
  return <Spinner />;
}
