import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Boxes } from "lucide-react";
import FilterBar from "@/components/app/FilterBar";
import KpiCard from "@/components/app/KpiCard";
import RecordsTable from "@/components/app/RecordsTable";
import { AtRiskProducts, AtRiskStores } from "@/components/app/RiskTables";
import StatusBadge from "@/components/app/StatusBadge";
import StatusDonut from "@/components/app/StatusDonut";
import StackedBars from "@/components/app/StackedBars";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import { dashboard, record } from "./fixtures";

describe("Button", () => {
  it("is the black pill by default", () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveClass("bg-black", "text-white", "rounded-full");
  });
  it("disables itself and announces busy while loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
  it("renders a link when given an href", () => {
    render(<Button href="/dashboard/">Open</Button>);
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", expect.stringMatching(/^\/dashboard\/?$/));
  });
});

describe("KpiCard and StatusBadge", () => {
  it("shows label, value and hint", () => {
    render(<KpiCard label="In stock" value="595" hint="63.6%" icon={Boxes} accent="green" />);
    expect(screen.getByTestId("kpi-in-stock")).toHaveTextContent("595");
    expect(screen.getByText("63.6%")).toBeInTheDocument();
  });
  it.each([["In Stock", "bg-emerald-500"], ["Low Stock", "bg-amber-500"], ["Out of Stock", "bg-red-500"]] as const)("%s badge is colour coded", (status, cls) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(status)).toHaveClass(cls);
  });
});

describe("RecordsTable", () => {
  it("lists records with state, quantity, price and date", () => {
    render(<RecordsTable records={[record(), record({ store_name: "Cozmo Dabouq", availability_status: "Low Stock", quantity_on_shelf: 2, shelf_price_jod: 6.9 })]} total={2} asOf="2026-08-25" />);
    const table = screen.getByTestId("records");
    expect(table).toHaveTextContent("Showing 2 of 2. Data as of 25 Aug 2026.");
    expect(within(table).getAllByRole("row")).toHaveLength(3); // header + 2
    expect(table).toHaveTextContent("JOD 6.90");
    expect(table).toHaveTextContent("19 Aug 2026");
    expect(within(table).getByText("Low Stock")).toBeInTheDocument();
  });
  it("caps visible rows but reports the real total", () => {
    const many = Array.from({ length: 40 }, (_, i) => record({ store_name: `Store ${i}` }));
    render(<RecordsTable records={many} total={120} asOf="2026-08-25" />);
    expect(screen.getByTestId("records")).toHaveTextContent("Showing 25 of 120");
  });
  it("renders nothing without records", () => {
    const { container } = render(<RecordsTable records={[]} total={0} asOf="" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("risk tables and charts", () => {
  it("shows products and stores to watch", () => {
    const d = dashboard();
    render(<><AtRiskProducts rows={d.at_risk_products} /><AtRiskStores rows={d.at_risk_stores} /></>);
    expect(screen.getByText("Full Cream Milk Powder")).toBeInTheDocument();
    expect(screen.getByText("41%")).toBeInTheDocument();
    expect(screen.getByText("Irbid Mall Market")).toBeInTheDocument();
  });
  it("explains empty results", () => {
    render(<AtRiskProducts rows={[]} />);
    expect(screen.getByText("Nothing is at risk for these filters.")).toBeInTheDocument();
  });
  it("donut shows the total and each state", () => {
    render(<StatusDonut data={dashboard().status_split} />);
    expect(screen.getByLabelText(/936 listings/)).toBeInTheDocument();
    expect(screen.getByText("Low Stock")).toBeInTheDocument();
    expect(screen.getByText(/194/)).toBeInTheDocument();
  });
  it("donut and bars handle no data", () => {
    render(<><StatusDonut data={[{ status: "In Stock", count: 0, pct: 0 }]} /><StackedBars data={[]} label="x" /></>);
    expect(screen.getAllByText("No listings match these filters.")).toHaveLength(2);
  });
});

describe("FilterBar and Select", () => {
  it("emits changes and resets", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(<FilterBar options={dashboard().options} value={{}} onChange={onChange} />);
    expect(screen.getByRole("button", { name: /Reset/ })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("City"), "Amman");
    expect(onChange).toHaveBeenLastCalledWith({ city: "Amman" });
    rerender(<FilterBar options={dashboard().options} value={{ city: "Amman", status: "Low Stock" }} onChange={onChange} />);
    await user.selectOptions(screen.getByLabelText("City"), "");
    expect(onChange).toHaveBeenLastCalledWith({ city: undefined, status: "Low Stock" });
    await user.click(screen.getByRole("button", { name: /Reset/ }));
    expect(onChange).toHaveBeenLastCalledWith({});
  });
  it("select lists the options", () => {
    render(<Select label="X" name="x" options={[{ value: "a", label: "A" }]} emptyLabel="All" />);
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["All", "A"]);
  });
});
