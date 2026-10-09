import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), usePathname: () => "/en/inbox/", useSearchParams: () => new URLSearchParams() }));
const api = vi.hoisted(() => ({
  fetchInboxConfig: vi.fn(), fetchMessages: vi.fn(), fetchMessage: vi.fn(), fetchReview: vi.fn(), fetchActivity: vi.fn(),
  startSync: vi.fn(), approveItem: vi.fn(), rejectItem: vi.fn(), editItem: vi.fn(), retryItem: vi.fn(),
}));
vi.mock("@/lib/api/inbox", () => api);

import ActivityView from "@/components/inbox/ActivityView";
import InboxView from "@/components/inbox/InboxView";
import ReviewView from "@/components/inbox/ReviewView";
import AppSidebar from "@/components/app/AppSidebar";
import type { MessageDetail } from "@/lib/api/inbox";
import { ApiError } from "@/lib/api/types";
import { renderI18n } from "./render";

vi.mock("@/lib/auth/SessionProvider", () => ({ useSession: () => ({ session: { email: "rev@medgan.ai" }, signOut: vi.fn() }) }));

const wrap = (ui: React.ReactElement, locale: "en" | "ar" = "en") => renderI18n(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>, locale);

const summary = (over = {}) => ({ message_id: "m1", status: "EXECUTED", sender: "layla@medgan.ai", sender_name: "Layla Omar", subject: "Q4 sales report", received_at: "2026-10-05T08:30:00Z", action: "CREATE_TASK", route: "auto", task_id: "t9", task_url: "https://app.clickup.com/t/t9", error_code: null, ...over });
const detail = (over: Partial<MessageDetail> = {}): MessageDetail => ({
  ...summary(), body_excerpt: "Please prepare the Q4 sales report", can_approve: false, problems: [],
  proposal: {
    action: "CREATE_TASK", route: "auto", reasons: [], version: 1, edited_by: null, matches: [{ task_id: "t2", name: "Website homepage banner redesign", url: "https://app.clickup.com/t/t2", status: "to do", score: 0.55, exact_marker: false }],
    resolved: { title: "Prepare the Q4 sales report", description: "Prepare it", assignee_id: "103", assignee_label: "Sara Nasser", priority: 2, priority_source: "email", due_date: "2026-10-25", status: "to do", problems: [] },
    triage: { action: "CREATE_TASK", confidence: 0.92, rationale: "clear request", task: { title: "Prepare the Q4 sales report", description: "Prepare it", assignee: "Sara Nasser", priority: "high", due_date: "2026-10-25", status: null }, target_task_id: null, reply: null, missing_fields: [], sensitive: false, sensitivity_reasons: [] },
  },
  execution: { task_id: "t9", task_url: "https://app.clickup.com/t/t9", summary: "created 'Prepare the Q4 sales report'" }, error: null, draft: null,
  audit: [{ message_id: "m1", at: "2026-10-05T08:31:00.000Z", id: "a2", event: "executed", actor: "policy:auto" }, { message_id: "m1", at: "2026-10-05T08:30:59.000Z", id: "a1", event: "received", actor: "system" }], ...over,
} as MessageDetail);
const reviewItem = (over: Partial<MessageDetail> = {}) => detail({ status: "PENDING_REVIEW", execution: null, can_approve: true, ...over, proposal: { ...detail().proposal!, route: "review", reasons: ["possible duplicate of 'Website homepage banner redesign' (55% match)"] } });
const config = { mailbox: "xpand@medgan.ai", outlook_mode: "sample", clickup_mode: "api", reviewer_group: "inbox-reviewers", clickup_list_url: "https://app.clickup.com/1/v/li/2", members: [{ id: "103", name: "Sara Nasser", email: "sara@medgan.ai" }, { id: "102", name: "Ahmad Haddad", email: "ahmad@medgan.ai" }], statuses: ["to do", "in progress"], policy: {} };

beforeEach(() => { Object.values(api).forEach((f) => f.mockReset()); api.fetchInboxConfig.mockResolvedValue(config); });

describe("InboxView", () => {
  it("lists emails, labels sample mode, and shows the proposal, real field values and the ClickUp link", async () => {
    api.fetchMessages.mockResolvedValue({ messages: [summary(), summary({ message_id: "m2", subject: "Thanks", status: "IGNORED", action: "IGNORE", sender_name: "Ahmad" })], sync: { state: "done", fetched: 8, new: 8, duplicates: 0, failed: 0 }, mode: { outlook: "sample", clickup: "api" } });
    api.fetchMessage.mockResolvedValue(detail());
    wrap(<InboxView />);
    expect(await screen.findByRole("note")).toHaveTextContent("SAMPLE MODE: the mailbox is a clearly labelled test adapter");
    const list = screen.getByRole("list", { name: "Inbox" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(await screen.findByTestId("proposal-view")).toHaveTextContent("Sara Nasser");
    expect(screen.getByTestId("sync-status")).toHaveTextContent("Last sync: 8 emails, 8 new, 0 already known.");
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in ClickUp/ })).toHaveAttribute("href", "https://app.clickup.com/t/t9");
    expect(screen.getByText("55% match")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open the ClickUp list/ })).toBeInTheDocument();
  });

  it("marks defaults and unknown values honestly instead of inventing them", async () => {
    const d = detail();
    d.proposal!.resolved = { ...d.proposal!.resolved!, assignee_id: null, assignee_label: null, priority_source: "configured_default", priority: 3, due_date: null, problems: [] };
    d.proposal!.triage.task = { ...d.proposal!.triage.task!, assignee: "Nobody Here", due_date: null };
    api.fetchMessages.mockResolvedValue({ messages: [summary()], sync: null, mode: { outlook: "graph", clickup: "api" } });
    api.fetchMessage.mockResolvedValue(d);
    wrap(<InboxView />);
    const view = await screen.findByTestId("proposal-view");
    expect(view).toHaveTextContent("Nobody Here: no matching member");
    expect(view).toHaveTextContent("Normal (default)");
    expect(view).toHaveTextContent("Not stated");
    expect(screen.queryByRole("note")).not.toBeInTheDocument(); // real Outlook: no sample banner
    expect(screen.getByTestId("sync-status")).toHaveTextContent("Not synced yet");
  });

  it("starts a sync and shows progress", async () => {
    api.fetchMessages.mockResolvedValue({ messages: [], sync: null, mode: { outlook: "graph", clickup: "api" } });
    api.startSync.mockResolvedValue({ state: "running" });
    wrap(<InboxView />);
    expect(await screen.findByText(/No emails yet/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Sync inbox" }));
    expect(api.startSync).toHaveBeenCalledTimes(1);
  });

  it("shows a failed message with its error and a Retry that only appears when it can be retried", async () => {
    api.fetchMessages.mockResolvedValue({ messages: [summary({ status: "FAILED", error_code: "timeout" })], sync: null, mode: { outlook: "graph", clickup: "api" } });
    api.fetchMessage.mockResolvedValue(detail({ status: "FAILED", execution: null, error: { code: "timeout", message: "no answer", retryable: true, stage: "execute", at: "x" } }));
    api.retryItem.mockResolvedValue({});
    wrap(<InboxView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("timeout");
    await userEvent.setup().click(screen.getByRole("button", { name: /Retry/ }));
    expect(api.retryItem).toHaveBeenCalledWith("m1");
  });

  it("a permission error is explained", async () => {
    api.fetchMessages.mockRejectedValue(new ApiError(403, "x", undefined, "forbidden"));
    wrap(<InboxView />);
    expect(await screen.findByText("You do not have permission to do this.")).toBeInTheDocument();
  });

  it("renders in Arabic", async () => {
    api.fetchMessages.mockResolvedValue({ messages: [summary()], sync: { state: "done", fetched: 8, new: 8, duplicates: 0, failed: 0 }, mode: { outlook: "sample", clickup: "api" } });
    api.fetchMessage.mockResolvedValue(detail());
    wrap(<InboxView />, "ar");
    expect(await screen.findByRole("button", { name: "مزامنة البريد" })).toBeInTheDocument();
    expect(await screen.findByRole("note")).toHaveTextContent("وضع تجريبي");
    expect(await screen.findByText("عالية")).toBeInTheDocument();
  });
});

describe("ReviewView", () => {
  it("shows why it needs a person, and Approve runs only the server action", async () => {
    api.fetchReview.mockResolvedValue({ items: [reviewItem()] });
    api.approveItem.mockResolvedValue({ status: "EXECUTED" });
    wrap(<ReviewView />);
    const card = await screen.findByTestId("review-card");
    expect(card).toHaveTextContent("possible duplicate of 'Website homepage banner redesign'");
    await userEvent.setup().click(within(card).getByRole("button", { name: "Approve" }));
    expect(api.approveItem).toHaveBeenCalledWith("m1");
    expect(await screen.findByText("Approved and executed.")).toBeInTheDocument();
  });

  it("disables Approve and explains what is missing when the proposal cannot run yet", async () => {
    api.fetchReview.mockResolvedValue({ items: [reviewItem({ can_approve: false, problems: ["missing assignee"] })] });
    wrap(<ReviewView />);
    const card = await screen.findByTestId("review-card");
    expect(within(card).getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(card).toHaveTextContent("Cannot approve yet: missing assignee");
    await userEvent.setup().click(within(card).getByRole("button", { name: "Approve" }));
    expect(api.approveItem).not.toHaveBeenCalled();
  });

  it("rejects with an optional reason and says nothing was executed", async () => {
    api.fetchReview.mockResolvedValue({ items: [reviewItem()] });
    api.rejectItem.mockResolvedValue({ status: "REJECTED" });
    wrap(<ReviewView />);
    const user = userEvent.setup();
    const card = await screen.findByTestId("review-card");
    await user.click(within(card).getByRole("button", { name: "Reject" }));
    await user.type(screen.getByLabelText("Reason (optional)"), "duplicate of an old task");
    await user.click(within(screen.getByRole("form", { name: "Reject this proposal" })).getByRole("button", { name: "Reject" }));
    expect(api.rejectItem).toHaveBeenCalledWith("m1", "duplicate of an old task");
    expect(await screen.findByText("Rejected. Nothing was executed.")).toBeInTheDocument();
  });

  it("edits real values (members and statuses come from ClickUp) and sends only the changes the reviewer made", async () => {
    api.fetchReview.mockResolvedValue({ items: [reviewItem()] });
    api.editItem.mockResolvedValue({ status: "EXECUTED" });
    wrap(<ReviewView />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit and approve", hidden: true });
    expect(within(dialog).getByRole("option", { name: "Ahmad Haddad" })).toBeInTheDocument();
    expect(within(dialog).getByText("Only real ClickUp members can be chosen.")).toBeInTheDocument();
    await user.selectOptions(within(dialog).getByLabelText(/Assignee/), "ahmad@medgan.ai");
    await user.click(within(dialog).getByRole("button", { name: "Save and approve" }));
    await waitFor(() => expect(api.editItem).toHaveBeenCalledTimes(1));
    expect(api.editItem.mock.calls[0][0]).toBe("m1");
    expect(api.editItem.mock.calls[0][1].task).toMatchObject({ assignee: "ahmad@medgan.ai", title: "Prepare the Q4 sales report" });
  });

  it("shows the server's reasons when an edit is rejected", async () => {
    api.fetchReview.mockResolvedValue({ items: [reviewItem()] });
    api.editItem.mockRejectedValue(new ApiError(422, "x", { error: { problems: ["assignee 'Zed' is not a member of the workspace"] }, }, "invalid"));
    wrap(<ReviewView />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    await user.click(within(screen.getByRole("dialog", { name: "Edit and approve", hidden: true })).getByRole("button", { name: "Save and approve" }));
    expect(await screen.findByText("assignee 'Zed' is not a member of the workspace")).toBeInTheDocument();
  });

  it("an unauthorised or already-handled action is explained", async () => {
    api.fetchReview.mockResolvedValue({ items: [reviewItem()] });
    api.approveItem.mockRejectedValueOnce(new ApiError(403, "x", undefined, "forbidden")).mockRejectedValueOnce(new ApiError(409, "x", undefined, "conflict"));
    wrap(<ReviewView />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText("You do not have permission to do this.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("This item was already handled.")).toBeInTheDocument();
  });

  it("is empty when nothing waits, and works in Arabic", async () => {
    api.fetchReview.mockResolvedValue({ items: [] });
    const { unmount } = wrap(<ReviewView />);
    expect(await screen.findByText("Nothing is waiting for review.")).toBeInTheDocument();
    unmount();
    api.fetchReview.mockResolvedValue({ items: [reviewItem()] });
    wrap(<ReviewView />, "ar");
    expect(await screen.findByRole("button", { name: "موافقة" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "تعديل" })).toBeInTheDocument();
  });
});

describe("ActivityView and navigation", () => {
  it("shows the audit trail with the email subject and filters it", async () => {
    api.fetchActivity.mockResolvedValue({ events: [
      { message_id: "m1", at: "2026-10-05T08:31:00.000Z", id: "a2", event: "executed", actor: "policy:auto", action: "CREATE_TASK", outcome: "ok", task_id: "t9" },
      { message_id: "m1", at: "2026-10-05T08:30:00.000Z", id: "a1", event: "received", actor: "system" },
      { message_id: "m3", at: "2026-10-05T08:29:00.000Z", id: "a0", event: "unauthorized", actor: "outsider@medgan.ai", outcome: "denied" },
    ] });
    api.fetchMessages.mockResolvedValue({ messages: [summary()], sync: null, mode: { outlook: "graph", clickup: "api" } });
    wrap(<ActivityView />);
    const table = await screen.findByTestId("activity-table");
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(table).toHaveTextContent("Executed");
    expect(table).toHaveTextContent("Denied: not allowed");
    expect(table).toHaveTextContent("Q4 sales report");
    await userEvent.setup().type(screen.getByRole("searchbox"), "outsider");
    expect(within(table).getAllByRole("row")).toHaveLength(2);
  });

  it("the sidebar groups Inbox Automation next to the Availability pages", () => {
    wrap(<AppSidebar />);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getByText("Inbox Automation")).toBeInTheDocument();
    for (const [name, href] of [["Dashboard", "/en/dashboard/"], ["Assistant", "/en/assistant/"], ["Inbox", "/en/inbox/"], ["Review queue", "/en/review/"], ["Activity", "/en/activity/"]]) {
      expect(within(nav).getByRole("link", { name })).toHaveAttribute("href", expect.stringMatching(new RegExp(`^${href.replace(/\//g, "\\/")}?$`)));
    }
  });
});
