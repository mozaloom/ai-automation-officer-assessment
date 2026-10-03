"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "@/lib/auth/SessionProvider";

/** Client-side route guard (static hosting has no server). The API enforces auth for real: this only avoids a flash of empty pages. */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, ready } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const hadSession = useRef(false);

  useEffect(() => {
    if (session) { hadSession.current = true; return; }
    if (!ready) return;
    // Lost the session while using the app (sign out or expiry): plain login page. First visit: remember where to return to.
    router.replace(hadSession.current ? "/login/" : `/login/?next=${encodeURIComponent(pathname)}`);
  }, [ready, session, router, pathname]);

  if (!ready || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status" aria-label="Loading">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-blue/20 border-t-brand-blue" />
      </div>
    );
  }
  return <>{children}</>;
}
