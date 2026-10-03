import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StreamEvent } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";

const router = { replace: vi.fn(), push: vi.fn() };
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/en/dashboard/", useSearchParams: () => search }));

const streamAnswer = vi.fn();
vi.mock("@/lib/api/stream", () => ({ streamAnswer: (...args: unknown[]) => streamAnswer(...args) }));
const fetchDashboard = vi.fn();
vi.mock("@/lib/api/availability", () => ({ fetchDashboard: (...args: unknown[]) => fetchDashboard(...args) }));

import ChatPanel from "@/components/app/ChatPanel";
import DashboardView from "@/components/app/DashboardView";
import { MESSAGES } from "@/lib/i18n/messages";
import { askResponse, dashboard, record } from "./fixtures";
import { renderI18n } from "./render";

type Opts = { prompt: string; sessionId: string; locale: string; signal: AbortSignal; onEvent: (e: StreamEvent) => void };

/** A stream the test drives by hand: push events, then finish or fail. */
function controlled() {
  let opts!: Opts;
  let end!: { resolve: () => void; reject: (e: unknown) => void };
  streamAnswer.mockImplementation((o: Opts) => new Promise<void>((resolve, reject) => {
    opts = o; end = { resolve, reject };
    o.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  }));
  return {
    get opts() { return opts; },
    push: (e: StreamEvent) => act(async () => { opts.onEvent(e); await new Promise((r) => requestAnimationFrame(() => r(null))); }),
    finish: () => act(async () => { end.resolve(); }),
    fail: (e: unknown) => act(async () => { end.reject(e); }),
  };
}
const inLog = () => within(screen.getByRole("log"));
const done = (over = {}) => ({ type: "done" as const, ...askResponse(over) });

beforeEach(() => { streamAnswer.mockReset(); fetchDashboard.mockReset(); router.replace.mockReset(); search = new URLSearchParams(); });

describe("ChatPanel streaming (English)", () => {
  const ask = async (text = "Where is olive oil?") => {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Your question"), text);
    await user.keyboard("{Enter}");
    return user;
  };

  it("shows the question, then the records before the text, then the text as it arrives, then the verified answer", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    await ask();
    expect(screen.getByText("Where is olive oil?")).toBeInTheDocument();
    expect(inLog().getByText("Searching the POS data…")).toBeInTheDocument();
    expect(s.opts).toMatchObject({ prompt: "Where is olive oil?", locale: "en" });
    expect(s.opts.sessionId).toHaveLength(36);

    await s.push({ type: "records", records: [record()], queries: [], record_count: 1, data_as_of: "2026-08-25" });
    expect(screen.getByTestId("records")).toBeInTheDocument();
    expect(screen.queryByText(/In Stock/)).not.toBeInTheDocument();

    await s.push({ type: "delta", text: "It is **in " });
    await s.push({ type: "delta", text: "stock** at Sameh Mall Khalda." });
    expect(screen.getByText("in stock")).toBeInTheDocument(); // markdown rendered while streaming
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(inLog().queryByText("Searching the POS data…")).not.toBeInTheDocument();

    await s.push(done({ answer: "It is **in stock** at Sameh Mall Khalda." }));
    await s.finish();
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Answer ready.");
  });

  it("sends with Enter but not Shift+Enter, ignores empty input and clears the box", async () => {
    controlled();
    renderI18n(<ChatPanel />);
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    const user = userEvent.setup();
    await user.type(box, "   ");
    await user.keyboard("{Enter}");
    expect(streamAnswer).not.toHaveBeenCalled();
    await user.clear(box);
    await user.type(box, "line one{Shift>}{Enter}{/Shift}line two");
    expect(streamAnswer).not.toHaveBeenCalled();
    await user.keyboard("{Enter}");
    expect(streamAnswer).toHaveBeenCalledTimes(1);
    expect(streamAnswer.mock.calls[0][0].prompt).toBe("line one\nline two");
    expect(box).toHaveValue("");
  });

  it("sends a sample question when it is clicked", async () => {
    controlled();
    renderI18n(<ChatPanel />);
    await userEvent.setup().click(screen.getByRole("button", { name: MESSAGES.en.assistant.samples[0] }));
    expect(streamAnswer.mock.calls[0][0].prompt).toBe(MESSAGES.en.assistant.samples[0]);
  });

  it("Stop cancels the request, keeps the partial answer and lets the user ask again", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    const user = await ask();
    await s.push({ type: "delta", text: "Half an answer" });
    await user.click(screen.getByRole("button", { name: "Stop" }));
    expect(s.opts.signal.aborted).toBe(true);
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument());
    expect(screen.getByText("Half an answer")).toBeInTheDocument();
    expect(screen.getByText("Stopped.", { selector: "p" })).toBeInTheDocument();
  });

  it("explains a failure in plain words and retries the same question without repeating it", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    const user = await ask("Tahini in Irbid?");
    await s.fail(new ApiError(200, "raw detail", undefined, "agent_error"));
    expect(await inLog().findByText("The assistant could not answer right now. Please try again in a moment.")).toBeInTheDocument();
    expect(screen.queryByText("raw detail")).not.toBeInTheDocument();

    const second = controlled();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(second.opts.prompt).toBe("Tahini in Irbid?");
    expect(screen.getAllByText("Tahini in Irbid?")).toHaveLength(1);
    await second.push(done({ answer: "Found it." }));
    await second.finish();
    expect(await screen.findByText("Found it.")).toBeInTheDocument();
  });

  it.each([
    [new ApiError(429, "x"), "Too many requests. Please wait a moment and try again."],
    [new ApiError(401, "x"), "Your session has expired. Please sign in again."],
    [new ApiError(502, "x"), "The service is temporarily unavailable. Please try again."],
    [new ApiError(200, "x", undefined, "stream_interrupted"), "The answer was interrupted."],
    [new TypeError("Failed to fetch"), "Could not reach the service. Check your connection and try again."],
  ])("describes %#", async (error, text) => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    await ask();
    await s.fail(error);
    expect(await inLog().findByText(text)).toBeInTheDocument();
  });

  it("warns when a summary could not be verified", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    await ask();
    await s.push(done({ grounded: false, answer: "Please rely on the records." }));
    await s.finish();
    expect(await screen.findByText(MESSAGES.en.assistant.unverified)).toBeInTheDocument();
  });

  it("a reset text (corrective retry) replaces the draft instead of adding to it", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    await ask();
    await s.push({ type: "delta", text: "Wrong draft" });
    await s.push({ type: "reset" });
    await s.push({ type: "delta", text: "Checked answer" });
    expect(screen.queryByText("Wrong draft")).not.toBeInTheDocument();
    expect(screen.getByText("Checked answer")).toBeInTheDocument();
  });

  it("New chat clears the conversation and starts a fresh session", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />);
    const user = await ask();
    const first = s.opts.sessionId;
    await s.push(done());
    await s.finish();
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.queryByText("Where is olive oil?")).not.toBeInTheDocument();
    controlled();
    await user.type(screen.getByLabelText("Your question"), "again");
    await user.keyboard("{Enter}");
    expect(streamAnswer.mock.calls[1][0].sessionId).not.toBe(first);
  });
});

describe("ChatPanel in Arabic", () => {
  it("is fully Arabic, sends the interface language and shows Arabic records", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />, "ar");
    expect(screen.getByRole("heading", { name: "مساعد التوافر" })).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("سؤالك"), "وين بلاقي طحينة بعمان؟");
    await user.keyboard("{Enter}");
    expect(s.opts).toMatchObject({ prompt: "وين بلاقي طحينة بعمان؟", locale: "ar" });
    expect(inLog().getByText("جارٍ البحث في بيانات نقاط البيع…")).toBeInTheDocument();
    await s.push({ type: "records", records: [record()], queries: [], record_count: 1, data_as_of: "2026-08-25" });
    await s.push(done({ answer: "الطحينة متوفرة." }));
    await s.finish();
    expect(await screen.findByText("الطحينة متوفرة.")).toBeInTheDocument();
    expect(screen.getByText("6.69 دينار")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "إرسال" })).toBeInTheDocument();
  });
  it("writes failures in Arabic", async () => {
    const s = controlled();
    renderI18n(<ChatPanel />, "ar");
    await userEvent.setup().type(screen.getByLabelText("سؤالك"), "س{Enter}");
    await s.fail(new ApiError(429, "x"));
    expect(await inLog().findByText("الطلبات كثيرة. انتظر قليلًا ثم حاول مجدّدًا.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "إعادة المحاولة" })).toBeInTheDocument();
  });
});

describe("DashboardView", () => {
  const wrap = (ui: React.ReactElement, locale: "en" | "ar" = "en") => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return renderI18n(<QueryClientProvider client={client}>{ui}</QueryClientProvider>, locale);
  };

  it("shows the numbers from the API and the as-of line", async () => {
    fetchDashboard.mockResolvedValue(dashboard());
    wrap(<DashboardView />);
    expect(await screen.findByTestId("kpi-listings")).toHaveTextContent("936");
    expect(screen.getByTestId("as-of")).toHaveTextContent("Latest recorded POS data as of 25 Aug 2026. Oldest record in view: 12 Aug 2026.");
    expect(fetchDashboard).toHaveBeenCalledWith({ city: undefined, category: undefined, status: undefined });
  });

  it("reads filters from the URL and writes changes back to it", async () => {
    search = new URLSearchParams("city=Irbid&status=Low%20Stock");
    fetchDashboard.mockResolvedValue(dashboard());
    wrap(<DashboardView />);
    await screen.findByTestId("kpi-listings");
    expect(fetchDashboard).toHaveBeenCalledWith({ city: "Irbid", category: undefined, status: "Low Stock" });
    expect(screen.getByLabelText("City")).toHaveValue("Irbid");
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Dairy" } });
    expect(router.replace).toHaveBeenCalledWith("/en/dashboard/?city=Irbid&category=Dairy&status=Low+Stock", { scroll: false });
    await userEvent.setup().click(screen.getByRole("button", { name: "Reset filters" }));
    expect(router.replace).toHaveBeenLastCalledWith("/en/dashboard/", { scroll: false });
  });

  it("renders the whole dashboard in Arabic with Arabic names and Jordanian dates", async () => {
    fetchDashboard.mockResolvedValue(dashboard());
    wrap(<DashboardView />, "ar");
    expect(await screen.findByRole("heading", { name: "لوحة توافر المنتجات" })).toBeInTheDocument();
    await screen.findByTestId("kpi-listings");
    expect(screen.getByTestId("as-of")).toHaveTextContent("أحدث بيانات مسجّلة من نقاط البيع كما في 25 آب 2026. أقدم سجلّ معروض بتاريخ 12 آب 2026.");
    const byCity = screen.getByRole("region", { name: "التوافر حسب المدينة" });
    expect(within(byCity).getByText("عمّان")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "منتجات تحتاج متابعة" })).toBeInTheDocument();
  });

  it("explains an error and retries", async () => {
    fetchDashboard.mockRejectedValueOnce(new ApiError(502, "x")).mockResolvedValue(dashboard());
    wrap(<DashboardView />);
    expect(await screen.findByText("The dashboard could not load")).toBeInTheDocument();
    expect(screen.getByText("The service is temporarily unavailable. Please try again.")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("kpi-listings")).toBeInTheDocument();
  });

  it("shows a loading state first", () => {
    fetchDashboard.mockReturnValue(new Promise(() => {}));
    wrap(<DashboardView />);
    expect(screen.getByLabelText("Loading dashboard")).toHaveAttribute("aria-busy", "true");
  });
});
