"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { BarChart3, MessageSquareText, ShieldCheck } from "lucide-react";
import Brand from "@/components/app/Brand";
import LoginForm from "@/components/auth/LoginForm";
import { useSession } from "@/lib/auth/SessionProvider";

const POINTS = [
  { icon: BarChart3, title: "See stock at a glance", body: "A dashboard over the latest POS data: in stock, low stock and out of stock across every city." },
  { icon: MessageSquareText, title: "Ask in plain language", body: "Ask where a product can be bought and get a short answer in seconds." },
  { icon: ShieldCheck, title: "Answers you can trust", body: "Every answer comes from the matching POS records, shown right beside it." },
];

export default function LoginPage() {
  const { session, ready } = useSession();
  const router = useRouter();
  useEffect(() => { if (ready && session) router.replace("/dashboard/"); }, [ready, session, router]);

  return (
    <div className="min-h-screen w-full bg-white lg:bg-[radial-gradient(ellipse_at_top_left,#e6f7fb,transparent_55%),radial-gradient(ellipse_at_bottom_right,#e3e6f6,transparent_55%)] lg:bg-[#f4f6fa] lg:p-5 xl:p-6">
      <div className="relative grid min-h-screen w-full bg-white lg:min-h-[calc(100vh-2.5rem)] lg:grid-cols-[1.45fr_1fr] lg:gap-2 lg:rounded-[28px] lg:p-3 lg:shadow-[0_30px_80px_-40px_rgba(40,20,90,0.35)] xl:min-h-[calc(100vh-3rem)]">
        <aside className="relative hidden flex-col justify-between overflow-hidden rounded-[20px] bg-gradient-to-br from-[#2D368F] via-[#2D368F] to-[#1F2564] p-10 text-white lg:flex" aria-label="About XPAND Availability">
          {/* Drifting colour blobs */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="animate-blob-a absolute -start-20 -top-28 h-[30rem] w-[30rem] rounded-full bg-[#21c1dc]/30 blur-3xl" />
            <div className="animate-blob-b absolute -end-24 top-1/3 h-[34rem] w-[34rem] rounded-full bg-[#4a56c4]/40 blur-3xl" />
            <div className="animate-blob-c absolute -bottom-28 start-1/4 h-[28rem] w-[28rem] rounded-full bg-[#21c1dc]/20 blur-3xl" />
          </div>
          {/* Sliding wave layers */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-[45%] overflow-hidden">
            <svg className="animate-wave-3 absolute bottom-0 left-0 h-full w-[200%]" viewBox="0 0 2880 320" preserveAspectRatio="none">
              <path d="M0,170 C240,110 480,230 720,170 C960,110 1200,230 1440,170 C1680,110 1920,230 2160,170 C2400,110 2640,230 2880,170 L2880,320 L0,320 Z" fill="#FFFFFF" fillOpacity="0.10" />
            </svg>
            <svg className="animate-wave-2 absolute bottom-0 left-0 h-full w-[200%]" viewBox="0 0 2880 320" preserveAspectRatio="none">
              <path d="M0,210 C300,150 540,260 720,210 C900,160 1140,260 1440,210 C1740,150 1980,260 2160,210 C2340,160 2580,260 2880,210 L2880,320 L0,320 Z" fill="#FFFFFF" fillOpacity="0.08" />
            </svg>
            <svg className="animate-wave-1 absolute bottom-0 left-0 h-full w-[200%]" viewBox="0 0 2880 320" preserveAspectRatio="none">
              <path d="M0,250 C360,200 600,300 720,250 C840,205 1080,300 1440,250 C1800,200 2040,300 2160,250 C2280,205 2520,300 2880,250 L2880,320 L0,320 Z" fill="#FFFFFF" fillOpacity="0.06" />
            </svg>
          </div>

          <div className="relative z-10 inline-flex items-center gap-4">
            <span className="rounded-2xl bg-white px-5 py-3 shadow-lg"><Image src="/logos/xpand-logo.svg" alt="XPAND" width={150} height={35} priority style={{ height: 35, width: "auto" }} /></span>
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-white/80">Availability</span>
          </div>
          <div className="relative z-10">
            <h2 className="max-w-md text-4xl font-bold leading-tight tracking-tight">Know where every product stands.</h2>
            <ul className="mt-10 space-y-6">
              {POINTS.map(({ icon: Icon, title, body }) => (
                <li key={title} className="flex gap-4">
                  <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                  <div><p className="font-semibold">{title}</p><p className="mt-1 max-w-sm text-sm leading-relaxed text-white/75">{body}</p></div>
                </li>
              ))}
            </ul>
          </div>
          <p className="relative z-10 text-xs text-white/60">Built for the XPAND marketing team.</p>
        </aside>

        <div className="relative flex min-h-screen flex-col lg:min-h-0">
          <div className="px-6 py-5 sm:px-8 lg:hidden"><Brand href="/login/" /></div>
          <main id="main" className="flex flex-1 items-center justify-center px-6 pb-16 pt-4 sm:px-8 lg:pb-12">
            <div className="w-full max-w-sm animate-slide-up">
              <Suspense fallback={null}><LoginForm /></Suspense>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
