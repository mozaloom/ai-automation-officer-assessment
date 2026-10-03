import { describe, expect, it } from "vitest";
import { clearSession, isExpired, loadSession, saveSession, type Session } from "@/lib/auth/session";

describe("session storage", () => {
  const session: Session = { email: "a@b.co", id_token: "i", access_token: "a", refresh_token: "r", expires_at: Date.now() + 3_600_000 };
  it("round-trips and clears", () => {
    saveSession(session);
    expect(loadSession()).toEqual(session);
    clearSession();
    expect(loadSession()).toBeNull();
  });
  it("ignores corrupt or incomplete data", () => {
    window.localStorage.setItem("xpand.availability.session.v1", "{not json");
    expect(loadSession()).toBeNull();
    window.localStorage.setItem("xpand.availability.session.v1", JSON.stringify({ email: "a" }));
    expect(loadSession()).toBeNull();
  });
  it("detects expiry with a skew", () => {
    expect(isExpired(null)).toBe(true);
    expect(isExpired({ ...session, expires_at: Date.now() - 1 })).toBe(true);
    expect(isExpired({ ...session, expires_at: Date.now() + 10_000 })).toBe(true); // inside the 30 s skew
    expect(isExpired(session)).toBe(false);
  });
});
