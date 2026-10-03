import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const router = { replace: vi.fn(), push: vi.fn() };
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/en/dashboard/", useSearchParams: () => search }));
const fetchDashboard = vi.fn();
const fetchRecords = vi.fn();
vi.mock("@/lib/api/availability", () => ({ fetchDashboard: (...a: unknown[]) => fetchDashboard(...a), fetchRecords: (...a: unknown[]) => fetchRecords(...a) }));
vi.mock("@/lib/api/stream", () => ({ streamAnswer: vi.fn() }));

import AssistantView from "@/components/app/AssistantView";
import DashboardView from "@/components/app/DashboardView";
import RecordsTable from "@/components/app/RecordsTable";
import StateBars from "@/components/app/StateBars";
import StockShareBar from "@/components/app/StockShareBar";
import { WatchProducts } from "@/components/app/WatchTables";
import { useTable } from "@/lib/table";
import { renderHook } from "@testing-library/react";
import { dashboard, record } from "./fixtures";
import { renderI18n } from "./render";

beforeEach(() => { fetchDashboard.mockReset(); fetchRecords.mockReset(); router.replace.mockReset(); search = new URLSearchParams(); });
const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

describe("useTable", () => {
  const rows = [{ n: "b", v: 2 }, { n: "a", v: 10 }, { n: "c", v: 1 }];
  const sorters = { n: (r: (typeof rows)[0]) => r.n, v: (r: (typeof rows)[0]) => r.v };
  it("sorts numbers as numbers, flips direction, and searches", () => {
    const { result } = renderHook(() => useTable(rows, sorters, (r) => r.n, "en"));
    expect(result.current.rows.map((r) => r.n)).toEqual(["b", "a", "c"]); // untouched until sorted
    act(() => result.current.toggle("v"));
    expect(result.current.rows.map((r) => r.v)).toEqual([10, 2, 1]);
    act(() => result.current.toggle("v"));
    expect(result.current.rows.map((r) => r.v)).toEqual([1, 2, 10]);
    act(() => result.current.toggle("n"));
    expect(result.current.rows.map((r) => r.n)).toEqual(["c", "b", "a"]);
    act(() => result.current.setQuery(" A "));
    expect(result.current.rows.map((r) => r.n)).toEqual(["a"]);
  });
});

describe("sortable and searchable watch table", () => {
  const products = [
    { product_name: "Tahini", category: "Spreads", low_stock: 1, out_of_stock: 1, at_risk: 2, listings: 10, at_risk_pct: 20 },
    { product_name: "Basmati Rice", category: "Grains", low_stock: 4, out_of_stock: 6, at_risk: 10, listings: 20, at_risk_pct: 50 },
  ];
  it("sorts by a clicked column and says so to assistive technology", async () => {
    renderI18n(<WatchProducts rows={products} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Sort by Shortfall" }));
    expect(names()).toEqual(["Basmati Rice", "Tahini"]);
    expect(screen.getByRole("columnheader", { name: /Shortfall/ })).toHaveAttribute("aria-sort", "descending");
    await user.click(screen.getByRole("button", { name: "Sort by Shortfall" }));
    expect(names()).toEqual(["Tahini", "Basmati Rice"]);
  });
  it("filters by a search and explains an empty result; Arabic search finds Arabic names", async () => {
    const { unmount } = renderI18n(<WatchProducts rows={products} />);
    const user = userEvent.setup();
    await user.type(screen.getByRole("searchbox"), "rice");
    expect(names()).toEqual(["Basmati Rice"]);
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText("No rows match your search.")).toBeInTheDocument();
    unmount();
    renderI18n(<WatchProducts rows={products} />, "ar");
    await userEvent.setup().type(screen.getByRole("searchbox"), "طحينة");
    expect(names()).toEqual(["طحينة"]);
  });
  it("opens the row's records when its name is clicked", async () => {
    const onDrill = vi.fn();
    renderI18n(<WatchProducts rows={products} onDrill={onDrill} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Show records for Tahini" }));
    expect(onDrill).toHaveBeenCalledWith({ product: "Tahini", title: "Tahini" });
  });
});

describe("records table", () => {
  const many = Array.from({ length: 12 }, (_, i) => record({ store_name: `Store ${i}`, quantity_on_shelf: i, product_name: "Tahini" }));
  it("sorts by quantity and only offers search for longer lists", async () => {
    const { unmount } = renderI18n(<RecordsTable records={many.slice(0, 3)} total={3} asOf="2026-08-25" />);
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    unmount();
    renderI18n(<RecordsTable records={many} total={12} asOf="2026-08-25" />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Sort by Qty" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Store 11");
    await user.type(screen.getByRole("searchbox"), "store 3");
    expect(screen.getAllByRole("row")).toHaveLength(2);
  });
  it("opens a full-screen view of the whole table and closes it again", async () => {
    const { container } = renderI18n(<RecordsTable records={many} total={12} asOf="2026-08-25" />);
    const user = userEvent.setup();
    const dialog = container.querySelector("dialog")!;
    expect(within(dialog).queryByRole("table")).not.toBeInTheDocument(); // content is mounted only while open
    await user.click(screen.getByRole("button", { name: "Full screen: Matching POS records" }));
    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getAllByRole("row").length).toBe(13);
    await user.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(dialog).not.toHaveAttribute("open");
  });
});

describe("click to filter", () => {
  it("a bar row toggles its filter and shows which one is selected", async () => {
    const onSelect = vi.fn();
    const { rerender } = renderI18n(<StateBars rows={[{ value: "Amman", name: "Amman", in_stock: 5, low_stock: 1, out_of_stock: 0 }, { value: "Irbid", name: "Irbid", in_stock: 2, low_stock: 0, out_of_stock: 0 }]} onSelect={onSelect} />);
    await userEvent.setup().click(screen.getByRole("button", { name: /Irbid/ }));
    expect(onSelect).toHaveBeenCalledWith("Irbid");
    expect(screen.getByRole("button", { name: /Amman/ })).toHaveAttribute("aria-pressed", "false");
    expect(rerender).toBeTypeOf("function");
  });
  it("segments carry exact numbers for hover", () => {
    renderI18n(<StateBars rows={[{ value: "Amman", name: "Amman", in_stock: 3, low_stock: 1, out_of_stock: 0 }]} />);
    expect(document.querySelector('[title="In stock: 3 (75.0%)"]')).not.toBeNull();
  });
  it("the stock-share bar filters by state", async () => {
    const onSelect = vi.fn();
    renderI18n(<StockShareBar data={dashboard().status_split} onSelect={onSelect} selected="Low Stock" />);
    expect(screen.getByRole("button", { name: /Low stock/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.setup().click(screen.getByRole("button", { name: /Out of stock/ }));
    expect(onSelect).toHaveBeenCalledWith("Out of Stock");
  });
});

describe("interactive dashboard", () => {
  const wrap = (locale: "en" | "ar" = "en") => renderI18n(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><DashboardView /></QueryClientProvider>, locale);

  it("clicking a city bar writes the filter to the URL, and clicking it again clears it", async () => {
    fetchDashboard.mockResolvedValue(dashboard());
    wrap();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Amman/ }));
    expect(router.replace).toHaveBeenCalledWith("/en/dashboard/?city=Amman", { scroll: false });
  });

  it("drilling into a product loads its records into a side panel", async () => {
    fetchDashboard.mockResolvedValue(dashboard());
    fetchRecords.mockResolvedValue({ filters: { product_name: "Full Cream Milk Powder" }, total: 1, truncated: false, records: [record({ product_name: "Full Cream Milk Powder" })], data_as_of: "2026-08-25" });
    wrap();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Show records for Full Cream Milk Powder" }));
    await waitFor(() => expect(fetchRecords).toHaveBeenCalledWith({ city: undefined, category: undefined, status: undefined, product: "Full Cream Milk Powder", store: undefined }));
    const panel = screen.getByRole("dialog", { name: "Full Cream Milk Powder", hidden: true });
    expect(await within(panel).findByText("Sameh Mall Khalda")).toBeInTheDocument();
    await userEvent.setup().click(within(panel).getByRole("button", { name: "Close" }));
    expect(panel).not.toHaveAttribute("open");
  });

  it("offers the records for the active filters, and warns when the list is truncated", async () => {
    search = new URLSearchParams("city=Irbid");
    fetchDashboard.mockResolvedValue(dashboard());
    fetchRecords.mockResolvedValue({ filters: { city: "Irbid" }, total: 500, truncated: true, records: [record()], data_as_of: "2026-08-25" });
    wrap();
    await userEvent.setup().click(await screen.findByRole("button", { name: "View records" }));
    expect(await screen.findByText("Showing the first 1 records. Narrow the filters to see the rest.")).toBeInTheDocument();
    expect(fetchRecords).toHaveBeenCalledWith({ city: "Irbid", category: undefined, status: undefined, product: undefined, store: undefined });
  });

  it("explains a records failure", async () => {
    fetchDashboard.mockResolvedValue(dashboard());
    fetchRecords.mockRejectedValue(new Error("x"));
    wrap();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Show records for Irbid Mall Market" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The records could not load.");
  });

  it("every section can open full screen", async () => {
    fetchDashboard.mockResolvedValue(dashboard());
    wrap("ar");
    await userEvent.setup().click(await screen.findByRole("button", { name: "ملء الشاشة: التوافر حسب المدينة" }));
    expect(screen.getByRole("dialog", { name: "التوافر حسب المدينة", hidden: true })).toHaveAttribute("open");
  });
});

describe("assistant full-screen mode", () => {
  it("toggles with the button and leaves with Escape", async () => {
    renderI18n(<AssistantView />);
    const user = userEvent.setup();
    const button = screen.getByRole("button", { name: "Full screen" });
    expect(button).toHaveAttribute("aria-pressed", "false");
    await user.click(button);
    expect(screen.getByRole("button", { name: "Exit full screen" })).toHaveAttribute("aria-pressed", "true");
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Full screen" })).toHaveAttribute("aria-pressed", "false"));
    expect(document.body.style.overflow).toBe("");
  });
});
