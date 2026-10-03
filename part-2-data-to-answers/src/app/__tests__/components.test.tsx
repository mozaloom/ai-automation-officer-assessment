import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

let pathname = "/en/dashboard/";
vi.mock("next/navigation", () => ({ usePathname: () => pathname, useRouter: () => ({ replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

import Brand from "@/components/app/Brand";
import FilterBar from "@/components/app/FilterBar";
import FreshnessStrip from "@/components/app/FreshnessStrip";
import KpiStrip from "@/components/app/KpiStrip";
import LanguageToggle from "@/components/app/LanguageToggle";
import RecordsTable from "@/components/app/RecordsTable";
import StateBars from "@/components/app/StateBars";
import StatusBadge from "@/components/app/StatusBadge";
import StockShareBar from "@/components/app/StockShareBar";
import { WatchProducts, WatchStores } from "@/components/app/WatchTables";
import EmptyState from "@/components/ui/EmptyState";
import { dashboard, record } from "./fixtures";
import { I18nProvider } from "@/lib/i18n/I18nProvider";
import { renderI18n as render } from "./render";

beforeEach(() => { pathname = "/en/dashboard/"; });
const d = dashboard();

describe("Brand", () => {
  it("shows the XPAND logo and links to the dashboard in the current language", () => {
    render(<Brand />);
    expect(screen.getByRole("link", { name: "XPAND Availability home" })).toHaveAttribute("href", expect.stringMatching(/^\/en\/dashboard\/?$/));
    expect(screen.getByAltText("XPAND")).toHaveAttribute("src", expect.stringContaining("xpand-logo.svg"));
  });
  it("links to the Arabic dashboard in Arabic", () => {
    render(<Brand />, "ar");
    expect(screen.getByRole("link", { name: "الصفحة الرئيسية لتوافر المنتجات" })).toHaveAttribute("href", expect.stringMatching(/^\/ar\/dashboard\/?$/));
  });
});

describe("LanguageToggle", () => {
  it("offers the other language and keeps the page", () => {
    render(<LanguageToggle />);
    const link = screen.getByRole("link", { name: "Switch to Arabic" });
    expect(link).toHaveAttribute("href", "/ar/dashboard/");
    expect(link).toHaveAttribute("lang", "ar");
    expect(link).toHaveTextContent("العربية");
  });
  it("offers English from an Arabic page", () => {
    pathname = "/ar/assistant/";
    render(<LanguageToggle />, "ar");
    expect(screen.getByRole("link", { name: "التبديل إلى الإنجليزية" })).toHaveAttribute("href", "/en/assistant/");
  });
});

describe("KpiStrip", () => {
  it("shows the four numbers with their explanations", () => {
    render(<KpiStrip kpis={d.kpis} />);
    expect(screen.getByTestId("kpi-listings")).toHaveTextContent("936");
    expect(screen.getByTestId("kpi-in-stock")).toHaveTextContent("595");
    expect(screen.getByTestId("kpi-low-stock")).toHaveTextContent("194");
    expect(screen.getByTestId("kpi-out-of-stock")).toHaveTextContent("147");
    expect(screen.getByText("40 stores, 27 products, 12 cities")).toBeInTheDocument();
    expect(screen.getByText("63.6%")).toBeInTheDocument();
  });
  it("is written in Arabic with Western digits", () => {
    render(<KpiStrip kpis={d.kpis} />, "ar");
    expect(screen.getByText("عدد السجلّات")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-listings")).toHaveTextContent("936");
    expect(screen.getByText("40 متجرًا، 27 منتجًا، 12 مدينة")).toBeInTheDocument();
    expect(screen.getByText("نفدت الكمية")).toBeInTheDocument();
  });
});

describe("StockShareBar", () => {
  it("draws one bar sized by share and spells the numbers out", () => {
    render(<StockShareBar data={d.status_split} />);
    const bar = screen.getByRole("img", { name: "Share of 936 listings by stock state" });
    expect([...bar.children].map((c) => (c as HTMLElement).style.width)).toEqual(["63.6%", "20.7%", "15.7%"]);
    expect(screen.getByText("In stock")).toBeInTheDocument();
    expect(screen.getByText("595")).toBeInTheDocument();
  });
  it("says so when nothing matches", () => {
    render(<StockShareBar data={[]} />);
    expect(screen.getByText("No listings match these filters.")).toBeInTheDocument();
  });
  it("labels states in Arabic", () => {
    render(<StockShareBar data={d.status_split} />, "ar");
    expect(screen.getByText("متوفر")).toBeInTheDocument();
    expect(screen.getByText("كمية قليلة")).toBeInTheDocument();
  });
});

describe("StateBars", () => {
  const rows = [
    { name: "Irbid", in_stock: 10, low_stock: 0, out_of_stock: 0 },
    { name: "Amman", in_stock: 276, low_stock: 88, out_of_stock: 76 },
  ];
  it("ranks the largest first and writes each total", () => {
    render(<StateBars rows={rows} />);
    const items = screen.getAllByRole("listitem").filter((li) => li.getAttribute("aria-label"));
    expect(items.map((li) => li.getAttribute("aria-label"))).toEqual([
      "Amman: In stock 276, Low stock 88, Out of stock 76",
      "Irbid: In stock 10, Low stock 0, Out of stock 0",
    ]);
    expect(within(items[0]).getByText("440")).toBeInTheDocument();
  });
  it("shows an empty message", () => {
    render(<StateBars rows={[]} />);
    expect(screen.getByText("No listings match these filters.")).toBeInTheDocument();
  });
});

describe("FreshnessStrip", () => {
  it("shows one column per date with short dates", () => {
    render(<FreshnessStrip data={d.freshness} />);
    expect(screen.getByRole("img", { name: "Listings by last updated date" })).toBeInTheDocument();
    expect(screen.getByText("12 Aug")).toBeInTheDocument();
    expect(screen.getByText("74")).toBeInTheDocument();
  });
  it("uses Jordanian month names in Arabic", () => {
    render(<FreshnessStrip data={d.freshness} />, "ar");
    expect(screen.getByText("12 آب")).toBeInTheDocument();
  });
});

describe("watch tables", () => {
  it("lists products and stores with their shortfall", () => {
    render(<><WatchProducts rows={d.at_risk_products} /><WatchStores rows={d.at_risk_stores} /></>);
    expect(screen.getByText("Full Cream Milk Powder")).toBeInTheDocument();
    expect(screen.getByText("41.4%")).toBeInTheDocument();
    expect(screen.getByText("Irbid Mall Market")).toBeInTheDocument();
  });
  it("shows Arabic names for products, categories, stores and cities", () => {
    render(<><WatchProducts rows={d.at_risk_products} /><WatchStores rows={d.at_risk_stores} /></>, "ar");
    expect(screen.getByText("حليب بودرة كامل الدسم")).toBeInTheDocument();
    expect(screen.getByText("الألبان")).toBeInTheDocument();
    expect(screen.getByText("سوق إربد مول")).toBeInTheDocument();
    expect(screen.getByText("إربد")).toBeInTheDocument();
  });
  it("has an empty state", () => {
    render(<><WatchProducts rows={[]} /><WatchStores rows={[]} /></>);
    expect(screen.getAllByText("Nothing needs attention for these filters.")).toHaveLength(2);
  });
});

describe("StatusBadge", () => {
  it.each([["In Stock", "In stock"], ["Low Stock", "Low stock"], ["Out of Stock", "Out of stock"]] as const)("%s", (status, text) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });
  it("uses the fixed Arabic wording", () => {
    render(<StatusBadge status="Out of Stock" />, "ar");
    expect(screen.getByText("نفدت الكمية")).toBeInTheDocument();
  });
});

describe("RecordsTable", () => {
  const rows = [record(), record({ store_name: "Irbid Mall Market", city: "Irbid", area: "University Street", availability_status: "Out of Stock", quantity_on_shelf: 0, shelf_price_jod: 6.9, pack_size: "1.5 L" })];
  it("renders English records with JOD prices and a count", () => {
    render(<RecordsTable records={rows} total={5} asOf="2026-08-25" />);
    expect(screen.getByText("Showing 2 of 5. Data as of 25 Aug 2026.")).toBeInTheDocument();
    expect(screen.getByText("JOD 6.90")).toBeInTheDocument();
    expect(screen.getByText("Khalda, Amman")).toBeInTheDocument();
  });
  it("renders Arabic records with Arabic names, prices, dates and pack sizes", () => {
    render(<RecordsTable records={rows} total={5} asOf="2026-08-25" />, "ar");
    expect(screen.getByText("يُعرض 2 من أصل 5. البيانات كما في 25 آب 2026.")).toBeInTheDocument();
    expect(screen.getByText("6.90 دينار")).toBeInTheDocument();
    expect(screen.getByText("سامح مول - خلدا")).toBeInTheDocument();
    expect(screen.getByText("(1.5 لتر)")).toBeInTheDocument();
    expect(screen.getByText("شارع الجامعة، إربد")).toBeInTheDocument();
  });
  it("renders nothing without records", () => {
    const { container } = render(<RecordsTable records={[]} total={0} asOf="" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("FilterBar", () => {
  it("lists localized options and reports changes", async () => {
    const onChange = vi.fn();
    render(<FilterBar options={d.options} value={{}} onChange={onChange} />, "ar");
    expect(screen.getByRole("option", { name: "عمّان" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "الألبان" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "نفدت الكمية" })).toBeInTheDocument();
    await userEvent.setup().selectOptions(screen.getByLabelText("المدينة"), "Irbid");
    expect(onChange).toHaveBeenCalledWith({ city: "Irbid" });
  });
  it("shows Reset only while a filter is active, and clears everything", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<FilterBar options={d.options} value={{}} onChange={onChange} />);
    expect(screen.queryByRole("button", { name: "Reset filters" })).not.toBeInTheDocument();
    rerender(<I18nProvider locale="en"><FilterBar options={d.options} value={{ city: "Amman" }} onChange={onChange} /></I18nProvider>);
    await userEvent.setup().click(screen.getByRole("button", { name: "Reset filters" }));
    expect(onChange).toHaveBeenCalledWith({});
  });
});

describe("EmptyState", () => {
  it("shows title, body and action", () => {
    render(<EmptyState title="Nothing" body="Try later" action={<button>Go</button>} />);
    expect(screen.getByRole("heading", { name: "Nothing" })).toBeInTheDocument();
    expect(screen.getByText("Try later")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Go" })).toBeInTheDocument();
  });
});
