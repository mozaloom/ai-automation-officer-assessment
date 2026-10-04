// Token persistence in localStorage: id token (sent to the API), refresh token, email, expiry.
const KEY = "xpand.availability.session.v1";

export interface Session {
  email: string;
  id_token: string;
  access_token: string;
  refresh_token: string;
  expires_at: number;
}

export function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    return parsed.id_token && parsed.refresh_token && parsed.expires_at ? parsed : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session) {
  if (typeof window !== "undefined") window.localStorage.setItem(KEY, JSON.stringify(session));
}

export function clearSession() {
  if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
}

export function isExpired(session: Session | null, skewSeconds = 30): boolean {
  return !session || Date.now() > session.expires_at - skewSeconds * 1000;
}
