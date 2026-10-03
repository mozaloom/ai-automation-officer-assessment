import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, configureApi } from "@/lib/api/client";
import { ApiError } from "@/lib/api/types";

const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("apiFetch", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    configureApi({ getToken: () => "tok-1", refresh: async () => null, onUnauthorized: () => {} });
  });

  it("sends the raw ID token, JSON body and query string (empty values dropped)", async () => {
    fetchMock.mockImplementation(async () => reply(200, { ok: true }));
    await apiFetch("/dashboard", { query: { city: "Amman", status: undefined, category: "" } });
    await apiFetch("/ask", { method: "POST", body: { prompt: "hi" }, headers: { "x-session-id": "s".repeat(36) } });
    const [url1, init1] = fetchMock.mock.calls[0];
    expect(url1).toBe("/dashboard?city=Amman");
    expect(init1.headers.Authorization).toBe("tok-1");
    const [, init2] = fetchMock.mock.calls[1];
    expect(init2.method).toBe("POST");
    expect(init2.headers["Content-Type"]).toBe("application/json");
    expect(init2.headers["x-session-id"]).toHaveLength(36);
    expect(JSON.parse(init2.body)).toEqual({ prompt: "hi" });
    expect(init2.credentials).toBe("omit");
  });

  it("refreshes once on 401 and replays the request with the new token", async () => {
    const refresh = vi.fn().mockResolvedValue("tok-2");
    configureApi({ getToken: () => "tok-1", refresh });
    fetchMock.mockResolvedValueOnce(reply(401, { message: "Unauthorized" })).mockResolvedValueOnce(reply(200, { fine: 1 }));
    await expect(apiFetch("/dashboard")).resolves.toEqual({ fine: 1 });
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("tok-2");
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("shares one refresh between concurrent 401s", async () => {
    const refresh = vi.fn().mockResolvedValue("tok-2");
    configureApi({ getToken: () => "tok-1", refresh });
    fetchMock.mockImplementation(async (_u: string, init: RequestInit) => ((init.headers as Record<string, string>).Authorization === "tok-2" ? reply(200, {}) : reply(401, {})));
    await Promise.all([apiFetch("/a"), apiFetch("/b")]);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("signals unauthorized and shows a friendly message when refresh is impossible", async () => {
    const onUnauthorized = vi.fn();
    configureApi({ getToken: () => "tok-1", refresh: async () => null, onUnauthorized });
    fetchMock.mockResolvedValue(reply(401, { message: "Unauthorized" }));
    await expect(apiFetch("/dashboard")).rejects.toMatchObject({ status: 401, message: expect.stringContaining("session has expired") });
    expect(onUnauthorized).toHaveBeenCalled();
  });

  it("maps API error bodies to ApiError", async () => {
    fetchMock.mockResolvedValue(reply(502, { error: { code: "upstream_error", message: "Try again." } }));
    const err = await apiFetch("/ask").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 502, message: "Try again.", code: "upstream_error" });
  });

  it("falls back to a generic message for unknown failures", async () => {
    fetchMock.mockResolvedValue(new Response("boom", { status: 500 }));
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 500, message: "Request failed with 500" });
  });
});
