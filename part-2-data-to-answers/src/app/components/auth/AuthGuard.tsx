"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import Spinner from "@/components/ui/Spinner";
import { useSession } from "@/lib/auth/SessionProvider";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Client-side route guard (static hosting has no server). The API enforces auth for real: this only avoids a flash of empty pages. */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, ready } = useSession();
  const { href } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const hadSession = useRef(false);

  useEffect(() => {
    if (session) { hadSession.current = true; return; }
    if (!ready) return;
    // Lost the session while using the app (sign out or expiry): plain login page. First visit: remember where to return to.
    router.replace(hadSession.current ? href("/login/") : `${href("/login/")}?next=${encodeURIComponent(pathname)}`);
  }, [ready, session, router, pathname, href]);

  if (!ready || !session) return <Spinner />;
  return <>{children}</>;
}
