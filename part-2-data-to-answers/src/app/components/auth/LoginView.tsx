"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Brand from "@/components/app/Brand";
import LanguageToggle from "@/components/app/LanguageToggle";
import LoginForm from "@/components/auth/LoginForm";
import { useSession } from "@/lib/auth/SessionProvider";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function LoginView() {
  const { session, ready } = useSession();
  const { t, href } = useI18n();
  const router = useRouter();
  useEffect(() => { if (ready && session) router.replace(href("/dashboard/")); }, [ready, session, router, href]);

  return (
    <div className="min-h-dvh w-full bg-white lg:p-4">
      <div className="grid min-h-dvh w-full lg:min-h-[calc(100dvh-2rem)] lg:grid-cols-[1.3fr_1fr] lg:gap-4">
        <aside className="relative hidden flex-col justify-between overflow-hidden rounded-2xl bg-gradient-to-br from-[#2D368F] via-[#2D368F] to-[#1F2564] p-10 text-white lg:flex" aria-label={t.login.aboutLabel}>
          {/* Drifting colour blobs */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="animate-blob-a absolute -start-20 -top-28 h-[30rem] w-[30rem] rounded-full bg-[#21c1dc]/30 blur-3xl" />
            <div className="animate-blob-b absolute -end-24 top-1/3 h-[34rem] w-[34rem] rounded-full bg-[#4a56c4]/40 blur-3xl" />
            <div className="animate-blob-c absolute -bottom-28 start-1/4 h-[28rem] w-[28rem] rounded-full bg-[#21c1dc]/20 blur-3xl" />
          </div>
          {/* Sliding wave layers */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-[45%] overflow-hidden" dir="ltr">
            <svg className="animate-wave-3 absolute bottom-0 start-0 h-full w-[200%]" viewBox="0 0 2880 320" preserveAspectRatio="none">
              <path d="M0,170 C240,110 480,230 720,170 C960,110 1200,230 1440,170 C1680,110 1920,230 2160,170 C2400,110 2640,230 2880,170 L2880,320 L0,320 Z" fill="#FFFFFF" fillOpacity="0.10" />
            </svg>
            <svg className="animate-wave-2 absolute bottom-0 start-0 h-full w-[200%]" viewBox="0 0 2880 320" preserveAspectRatio="none">
              <path d="M0,210 C300,150 540,260 720,210 C900,160 1140,260 1440,210 C1740,150 1980,260 2160,210 C2340,160 2580,260 2880,210 L2880,320 L0,320 Z" fill="#FFFFFF" fillOpacity="0.08" />
            </svg>
            <svg className="animate-wave-1 absolute bottom-0 start-0 h-full w-[200%]" viewBox="0 0 2880 320" preserveAspectRatio="none">
              <path d="M0,250 C360,200 600,300 720,250 C840,205 1080,300 1440,250 C1800,200 2040,300 2160,250 C2280,205 2520,300 2880,250 L2880,320 L0,320 Z" fill="#FFFFFF" fillOpacity="0.06" />
            </svg>
          </div>

          <span className="relative z-10 inline-flex self-start rounded-xl bg-white px-5 py-3">
            <Image src="/logos/xpand-logo.svg" alt="XPAND" translate="no" width={150} height={35} priority style={{ height: 35, width: "auto" }} />
          </span>
          <p className="relative z-10 max-w-sm text-xl font-medium leading-snug text-white/90">{t.login.tagline}</p>
        </aside>

        <div className="relative flex min-h-dvh flex-col lg:min-h-0">
          <div className="flex items-center px-6 py-5 sm:px-8">
            <div className="lg:hidden"><Brand href={href("/login/")} /></div>
            <LanguageToggle className="ms-auto" />
          </div>
          <main id="main" className="flex flex-1 items-center justify-center px-6 pb-16 pt-2 sm:px-8 lg:pb-12">
            <div className="w-full max-w-sm">
              <Suspense fallback={null}><LoginForm /></Suspense>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
