"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { configureApi } from "@/lib/api/client";
import { refresh, signIn as cognitoSignIn } from "./cognito";
import { clearSession, isExpired, loadSession, saveSession, type Session } from "./session";

interface SessionContextValue {
  session: Session | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);
const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000;

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const ref = useRef<Session | null>(null);

  const apply = useCallback((next: Session | null) => {
    ref.current = next;
    setSession(next);
    if (next) saveSession(next);
    else clearSession();
  }, []);

  const refreshNow = useCallback(async (): Promise<string | null> => {
    const current = ref.current;
    if (!current) return null;
    try {
      const next = await refresh(current.email, current.refresh_token);
      apply(next);
      return next.id_token;
    } catch {
      apply(null);
      return null;
    }
  }, [apply]);

  // Hydrate from storage, refreshing silently when the saved token has expired.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = loadSession();
      ref.current = stored;
      if (stored && isExpired(stored)) await refreshNow();
      else if (stored) setSession(stored);
      if (!cancelled) setReady(true);
    })();
    return () => { cancelled = true; };
  }, [refreshNow]);

  // Keep the token fresh while the tab stays open.
  useEffect(() => {
    if (!session) return;
    const wait = Math.max(session.expires_at - Date.now() - REFRESH_BEFORE_EXPIRY_MS, 10_000);
    const timer = window.setTimeout(() => { void refreshNow(); }, wait);
    return () => window.clearTimeout(timer);
  }, [session, refreshNow]);

  useEffect(() => {
    configureApi({ getToken: () => ref.current?.id_token ?? null, refresh: refreshNow, onUnauthorized: () => apply(null) });
  }, [refreshNow, apply]);

  const signIn = useCallback(async (email: string, password: string) => {
    apply(await cognitoSignIn(email.trim().toLowerCase(), password));
  }, [apply]);

  const value = useMemo<SessionContextValue>(() => ({ session, ready, signIn, signOut: () => apply(null) }), [session, ready, signIn, apply]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
