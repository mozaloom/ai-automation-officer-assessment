"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, LogOut, Sparkles } from "lucide-react";
import { useSession } from "@/lib/auth/SessionProvider";
import Brand from "./Brand";

const NAV = [
  { key: "dashboard", label: "Dashboard", href: "/dashboard/", icon: LayoutDashboard },
  { key: "assistant", label: "Assistant", href: "/assistant/", icon: Sparkles },
] as const;

export default function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useSession();
  const isActive = (href: string) => pathname.startsWith(href.replace(/\/$/, ""));
  const handleSignOut = () => { signOut(); router.replace("/login/"); };

  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-e border-gray-100 bg-white/60 backdrop-blur lg:flex">
        <div className="border-b border-gray-100 px-5 py-4"><Brand /></div>
        <nav className="flex-1 space-y-1 p-4" aria-label="Main navigation">
          {NAV.map(({ key, label, href, icon: Icon }) => (
            <Link key={key} href={href} aria-current={isActive(href) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${isActive(href) ? "bg-brand-blue/[0.08] font-semibold text-brand-blue" : "text-text-dark hover:bg-brand-blue/5 hover:text-brand-blue"}`}>
              <Icon className="h-4 w-4" aria-hidden="true" /><span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="space-y-1 border-t border-gray-100 p-4">
          {session?.email && <p className="truncate px-3 py-1 text-xs text-text-gray" title={session.email}>{session.email}</p>}
          <button onClick={handleSignOut} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50">
            <LogOut className="h-4 w-4" aria-hidden="true" /><span>Sign out</span>
          </button>
        </div>
      </aside>

      <header className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-gray-100 bg-white/90 px-4 backdrop-blur lg:hidden">
        <Brand size="sm" />
        <button onClick={handleSignOut} className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50">
          <LogOut className="h-4 w-4" aria-hidden="true" /><span>Sign out</span>
        </button>
      </header>

      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-gray-100 bg-white/90 backdrop-blur lg:hidden" aria-label="Mobile navigation">
        {NAV.map(({ key, label, href, icon: Icon }) => (
          <Link key={key} href={href} aria-current={isActive(href) ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 py-3 text-[10px] font-medium transition-colors ${isActive(href) ? "text-brand-blue" : "text-text-gray hover:text-brand-blue"}`}>
            <Icon className="h-5 w-5" aria-hidden="true" /><span>{label}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
