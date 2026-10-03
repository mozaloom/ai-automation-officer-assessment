import { describe, expect, it } from "vitest";
import { formatDate, formatJod, formatNumber, formatPct, formatShortDate, statusVariant } from "@/lib/format";
import { clearSession, isExpired, loadSession, saveSession, type Session } from "@/lib/auth/session";

describe("format", () => {
  it("formats ISO dates without time zone drift", () => {
    expect(formatDate("2026-08-25")).toBe("25 Aug 2026");
    expect(formatDate("2026-01-05")).toBe("5 Jan 2026");
    expect(formatShortDate("2026-08-12")).toBe("12 Aug");
  });
  it("passes through unparseable dates", () => { expect(formatDate("soon")).toBe("soon"); expect(formatDate(undefined)).toBe(""); });
  it("formats numbers, percentages and prices", () => {
    expect(formatNumber(1234)).toBe("1,234");
    expect(formatPct(63.55)).toBe("63.5%".replace("63.5", (63.55).toFixed(1)));
    expect(formatJod(6.9)).toBe("JOD 6.90");
  });
  it("maps stock states to badge colours", () => {
    expect(statusVariant("In Stock")).toBe("green");
    expect(statusVariant("Low Stock")).toBe("amber");
    expect(statusVariant("Out of Stock")).toBe("red");
  });
});

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
