import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), usePathname: () => "/en/dashboard/", useSearchParams: () => new URLSearchParams() }));

import RecordsChart from "@/components/app/RecordsChart";
import RecordsTable from "@/components/app/RecordsTable";
import ErrorPage from "@/app/[locale]/error";
import { aggregate, wantsChart } from "@/lib/chart";
import { record } from "./fixtures";
import { renderI18n } from "./render";

const rows = [
  record({ store_name: "A", city: "Amman", quantity_on_shelf: 10, shelf_price_jod: 1 }),
  record({ store_name: "B", city: "Amman", quantity_on_shelf: 5, shelf_price_jod: 3, availability_status: "Low Stock" }),
  record({ store_name: "C", city: "Irbid", quantity_on_shelf: 1, shelf_price_jod: 2, availability_status: "Out of Stock" }),
];

describe("aggregate", () => {
  it("counts, sums, averages and finds the lowest price per group", () => {
    expect(aggregate(rows, "city", "count")).toEqual([{ key: "Amman", value: 2 }, { key: "Irbid", value: 1 }]);
    expect(aggregate(rows, "city", "quantity")).toEqual([{ key: "Amman", value: 15 }, { key: "Irbid", value: 1 }]);
    expect(aggregate(rows, "city", "avgPrice")).toEqual([{ key: "Irbid", value: 2 }, { key: "Amman", value: 2 }].sort((a, b) => b.value - a.value || a.key.localeCompare(b.key)));
    expect(aggregate(rows, "store_name", "minPrice").map((r) => r.key)).toEqual(["A", "C", "B"]); // cheapest first
    expect(aggregate([], "city", "count")).toEqual([]);
  });
});

describe("wantsChart", () => {
  it.each(["show a chart of tahini", "Plot prices by city", "give me a graph", "visualize stock", "ارسم مخطط للطحينة", "أريد رسم بياني"])("%s", (q) => expect(wantsChart(q)).toBe(true));
  it.each(["Where can I buy tea?", "chartreuse", "وين بلاقي شاي؟"])("not %s", (q) => expect(wantsChart(q)).toBe(false));
});

describe("RecordsChart", () => {
  it("draws bars with their values, and regroups and re-measures on change", async () => {
    renderI18n(<RecordsChart records={rows} />);
    const list = screen.getByRole("list", { name: "Number of records by city" });
    expect(within(list).getByText("Amman")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Measure"), "minPrice");
    await user.selectOptions(screen.getByLabelText("Group by"), "store_name");
    const next = screen.getByRole("list", { name: "Lowest price by store" });
    expect(within(next).getAllByRole("listitem")[0]).toHaveTextContent("JOD 1.00");
    await user.selectOptions(screen.getByLabelText("Group by"), "availability_status");
    expect(screen.getByText("Out of stock")).toBeInTheDocument();
  });
  it("is written in Arabic with Arabic names and prices", async () => {
    renderI18n(<RecordsChart records={rows} />, "ar");
    expect(screen.getByLabelText("التجميع حسب")).toBeInTheDocument();
    expect(screen.getByText("عمّان")).toBeInTheDocument();
    await userEvent.setup().selectOptions(screen.getByLabelText("المقياس"), "avgPrice");
    expect(screen.getAllByText(/دينار/).length).toBeGreaterThan(0);
  });
});

describe("records table chart view", () => {
  it("switches between table and chart, and can start as a chart", async () => {
    const { unmount } = renderI18n(<RecordsTable records={rows} total={3} asOf="2026-08-25" />);
    const user = userEvent.setup();
    expect(screen.getByRole("table")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chart" }));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("list", { name: /by city/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Table" }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    unmount();
    renderI18n(<RecordsTable records={rows} total={3} asOf="2026-08-25" defaultView="chart" />);
    expect(screen.getByRole("button", { name: "Chart" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("error page", () => {
  it("explains the failure in the visitor's language and can retry", async () => {
    const reset = vi.fn();
    renderI18n(<ErrorPage error={new Error("x")} reset={reset} />, "ar");
    expect(screen.getByRole("heading", { name: "تعذّر تحميل هذه الصفحة" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "إعادة التحميل" }));
    expect(reset).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "رجوع" })).toHaveAttribute("href", "/ar/dashboard/");
  });
});
