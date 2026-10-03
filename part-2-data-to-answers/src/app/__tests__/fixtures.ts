import type { AskResponse, DashboardData, PosRecord } from "@/lib/api/types";

export const record = (over: Partial<PosRecord> = {}): PosRecord => ({
  store_name: "Sameh Mall Khalda", store_type: "Hypermarket", area: "Khalda", city: "Amman", region: "Central",
  product_name: "Olive Oil Extra Virgin", category: "Cooking Oil", pack_size: "750 ml", quantity_on_shelf: 56,
  availability_status: "In Stock", shelf_price_jod: 6.69, last_updated: "2026-08-19", ...over,
});

export const dashboard = (over: Partial<DashboardData> = {}): DashboardData => ({
  filters: {}, as_of: "2026-08-25", oldest_update: "2026-08-12", dataset_as_of: "2026-08-25",
  options: { cities: ["Amman", "Irbid"], categories: ["Dairy", "Grains"], statuses: ["In Stock", "Low Stock", "Out of Stock"] },
  kpis: { listings: 936, stores: 40, products: 27, cities: 12, in_stock: 595, low_stock: 194, out_of_stock: 147, in_stock_pct: 63.6, low_stock_pct: 20.7, out_of_stock_pct: 15.7 },
  status_split: [{ status: "In Stock", count: 595, pct: 63.6 }, { status: "Low Stock", count: 194, pct: 20.7 }, { status: "Out of Stock", count: 147, pct: 15.7 }],
  by_city: [{ city: "Amman", in_stock: 276, low_stock: 88, out_of_stock: 76, total: 440 }],
  by_category: [{ category: "Dairy", in_stock: 10, low_stock: 5, out_of_stock: 2, total: 17 }],
  by_store_type: [],
  at_risk_products: [{ product_name: "Full Cream Milk Powder", category: "Dairy", low_stock: 26, out_of_stock: 10, at_risk: 36, listings: 87, at_risk_pct: 41.4 }],
  at_risk_stores: [{ store_name: "Irbid Mall Market", city: "Irbid", area: "University Street", low_stock: 8, out_of_stock: 8, at_risk: 16, listings: 31 }],
  freshness: [{ date: "2026-08-12", count: 33 }, { date: "2026-08-25", count: 74 }],
  ...over,
});

export const askResponse = (over: Partial<AskResponse> = {}): AskResponse => ({
  answer: "**Olive Oil Extra Virgin** is **In Stock** at Sameh Mall Khalda.", records: [record()], queries: [], record_count: 1,
  data_as_of: "2026-08-25", session_id: "s", grounded: true, ...over,
});
