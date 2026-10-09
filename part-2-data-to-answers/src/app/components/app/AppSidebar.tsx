"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { History, Inbox, LayoutDashboard, ListChecks, LogOut, MessageSquare } from "lucide-react";
import { useSession } from "@/lib/auth/SessionProvider";
import { useI18n } from "@/lib/i18n/I18nProvider";
import Brand from "./Brand";
import LanguageToggle from "./LanguageToggle";

const NAV = [
  { key: "dashboard", path: "/dashboard/", icon: LayoutDashboard },
  { key: "assistant", path: "/assistant/", icon: MessageSquare },
] as const;
const INBOX_NAV = [
  { key: "inbox", path: "/inbox/", icon: Inbox },
  { key: "review", path: "/review/", icon: ListChecks },
  { key: "activity", path: "/activity/", icon: History },
] as const;

export default function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useSession();
  const { t, href } = useI18n();
  const isActive = (path: string) => pathname.startsWith(href(path).replace(/\/$/, ""));
  const handleSignOut = () => { signOut(); router.replace(href("/login/")); };

  return (
    <>
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-e border-line bg-white lg:flex">
        <div className="px-5 py-5"><Brand /></div>
        <nav className="flex-1 space-y-0.5 px-3" aria-label={t.nav.main}>
          {NAV.map(({ key, path, icon: Icon }) => (
            <Link key={key} href={href(path)} aria-current={isActive(path) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${isActive(path) ? "bg-brand-blue/[0.08] font-semibold text-brand-blue" : "text-text-dark hover:bg-wash"}`}>
              <Icon className="h-4 w-4" aria-hidden="true" /><span>{t.nav[key]}</span>
            </Link>
          ))}
          <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wide text-text-gray">{t.inbox.group}</p>
          {INBOX_NAV.map(({ key, path, icon: Icon }) => (
            <Link key={key} href={href(path)} aria-current={isActive(path) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${isActive(path) ? "bg-brand-blue/[0.08] font-semibold text-brand-blue" : "text-text-dark hover:bg-wash"}`}>
              <Icon className="h-4 w-4" aria-hidden="true" /><span>{t.inbox.nav[key]}</span>
            </Link>
          ))}
        </nav>
        <div className="space-y-2 border-t border-line p-4">
          {session?.email && <p className="truncate text-xs text-text-gray" dir="ltr" title={session.email}>{session.email}</p>}
          <div className="flex items-center justify-between gap-2">
            <button onClick={handleSignOut} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-text-dark transition-colors hover:bg-wash">
              <LogOut className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" /><span>{t.nav.signOut}</span>
            </button>
            <LanguageToggle />
          </div>
        </div>
      </aside>

      <header className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-line bg-white px-4 lg:hidden">
        <Brand size="sm" />
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <button onClick={handleSignOut} aria-label={t.nav.signOut} className="rounded-md p-2 text-text-dark transition-colors hover:bg-wash">
            <LogOut className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
          </button>
        </div>
      </header>

      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-white pb-[env(safe-area-inset-bottom)] lg:hidden" aria-label={t.nav.mobile}>
        {[...NAV.map((n) => ({ ...n, label: t.nav[n.key] })), ...INBOX_NAV.map((n) => ({ ...n, label: t.inbox.nav[n.key] }))].map(({ key, path, icon: Icon, label }) => (
          <Link key={key} href={href(path)} aria-current={isActive(path) ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors ${isActive(path) ? "text-brand-blue" : "text-text-gray hover:text-text-dark"}`}>
            <Icon className="h-5 w-5" aria-hidden="true" /><span className="max-w-full truncate px-1">{label}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
