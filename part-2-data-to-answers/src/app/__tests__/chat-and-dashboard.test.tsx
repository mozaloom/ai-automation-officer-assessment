import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/availability", () => ({ askAssistant: vi.fn(), fetchDashboard: vi.fn() }));
import ChatPanel, { SAMPLE_QUESTIONS } from "@/components/app/ChatPanel";
import DashboardPage from "@/app/(app)/dashboard/page";
import { askAssistant, fetchDashboard } from "@/lib/api/availability";
import { askResponse, dashboard, record } from "./fixtures";

const ask = vi.mocked(askAssistant);
const dash = vi.mocked(fetchDashboard);
beforeEach(() => { ask.mockReset(); dash.mockReset(); });

describe("ChatPanel", () => {
  it("offers sample questions and sends one with a long enough session id", async () => {
    ask.mockResolvedValue(askResponse());
    render(<ChatPanel />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: SAMPLE_QUESTIONS[0] }));
    expect(await screen.findByText("Olive Oil Extra Virgin", { selector: "strong" })).toBeInTheDocument();
    expect(ask).toHaveBeenCalledWith(SAMPLE_QUESTIONS[0], expect.any(String));
    expect(ask.mock.calls[0][1].length).toBeGreaterThanOrEqual(33);
    expect(screen.getByTestId("records")).toHaveTextContent("Sameh Mall Khalda");
  });

  it("renders the answer as markdown and keeps the same session for follow-ups", async () => {
    ask.mockResolvedValue(askResponse());
    render(<ChatPanel />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Your question"), "Olive oil in Amman?");
    await user.click(screen.getByRole("button", { name: "Send question" }));
    await screen.findByTestId("records");
    await user.type(screen.getByLabelText("Your question"), "and low stock?");
    await user.click(screen.getByRole("button", { name: "Send question" }));
    await waitFor(() => expect(ask).toHaveBeenCalledTimes(2));
    expect(ask.mock.calls[0][1]).toBe(ask.mock.calls[1][1]);
  });

  it("does not send blank messages", async () => {
    render(<ChatPanel />);
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
  });

  it("shows ambiguity answers without a records table", async () => {
    ask.mockResolvedValue(askResponse({ answer: "Which tea do you mean: Black Tea Bags or Green Tea Bags?", records: [], record_count: 0 }));
    render(<ChatPanel />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Where can I buy tea?" }));
    expect(await screen.findByText(/Which tea do you mean/)).toBeInTheDocument();
    expect(screen.queryByTestId("records")).not.toBeInTheDocument();
  });

  it("warns when an answer could not be verified", async () => {
    ask.mockResolvedValue(askResponse({ grounded: false, answer: "I could not produce a fully verified summary." }));
    render(<ChatPanel />);
    await userEvent.setup().click(screen.getByRole("button", { name: SAMPLE_QUESTIONS[0] }));
    expect(await screen.findByText(/could not be fully verified/)).toBeInTheDocument();
  });

  it("shows failures inline and lets the user try again", async () => {
    ask.mockRejectedValueOnce(new Error("The service is temporarily unavailable. Please try again.")).mockResolvedValueOnce(askResponse());
    render(<ChatPanel />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: SAMPLE_QUESTIONS[1] }));
    expect(await screen.findByText(/temporarily unavailable/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your question"), "retry");
    await user.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByTestId("records")).toBeInTheDocument();
  });

  it("starts a fresh conversation and session", async () => {
    ask.mockResolvedValue(askResponse());
    render(<ChatPanel />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: SAMPLE_QUESTIONS[0] }));
    await screen.findByTestId("records");
    await user.click(screen.getByRole("button", { name: /New chat/ }));
    expect(screen.queryByTestId("records")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: SAMPLE_QUESTIONS[0] }));
    await waitFor(() => expect(ask).toHaveBeenCalledTimes(2));
    expect(ask.mock.calls[0][1]).not.toBe(ask.mock.calls[1][1]);
  });
});

function renderDashboard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>);
}

describe("DashboardPage", () => {
  it("shows the KPIs, freshness line and watch lists from the API", async () => {
    dash.mockResolvedValue(dashboard());
    renderDashboard();
    expect(await screen.findByTestId("kpi-listings")).toHaveTextContent("936");
    expect(screen.getByTestId("kpi-in-stock")).toHaveTextContent("595");
    expect(screen.getByTestId("kpi-low-stock")).toHaveTextContent("194");
    expect(screen.getByTestId("kpi-out-of-stock")).toHaveTextContent("147");
    expect(screen.getByTestId("as-of")).toHaveTextContent("25 Aug 2026");
    expect(screen.getByText("Full Cream Milk Powder")).toBeInTheDocument();
    expect(dash).toHaveBeenCalledWith({});
  });

  it("refetches with the chosen filters", async () => {
    dash.mockResolvedValueOnce(dashboard()).mockResolvedValueOnce(dashboard({ kpis: { ...dashboard().kpis, listings: 440 }, filters: { city: "Amman" } }));
    renderDashboard();
    await screen.findByTestId("kpi-listings");
    await userEvent.setup().selectOptions(screen.getByLabelText("City"), "Amman");
    await waitFor(() => expect(screen.getByTestId("kpi-listings")).toHaveTextContent("440"));
    expect(dash).toHaveBeenLastCalledWith({ city: "Amman" });
  });

  it("shows a retry state when the API fails", async () => {
    dash.mockRejectedValueOnce(new Error("The service is temporarily unavailable.")).mockResolvedValueOnce(dashboard());
    renderDashboard();
    expect(await screen.findByText("The dashboard could not load")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /Try again/ }));
    expect(await screen.findByTestId("kpi-listings")).toBeInTheDocument();
  });

  it("shows a loading skeleton first", () => {
    dash.mockReturnValue(new Promise(() => {}));
    renderDashboard();
    expect(screen.getByLabelText("Loading dashboard")).toBeInTheDocument();
    expect(within(screen.getByTestId("as-of")).queryByText(/25 Aug/)).toBeNull();
  });

  it("uses a record fixture shape matching the API", () => {
    expect(Object.keys(record()).sort()).toContain("availability_status");
  });
});
