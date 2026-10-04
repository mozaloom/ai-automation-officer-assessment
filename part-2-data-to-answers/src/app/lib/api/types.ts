export type StockStatus = "In Stock" | "Low Stock" | "Out of Stock";

export class ApiError extends Error {
  constructor(public status: number, message: string, public payload?: unknown, public code?: string) {
    super(message);
    this.name = "ApiError";
  }
}

export interface PosRecord {
  store_name: string;
  store_type: string;
  area: string;
  city: string;
  region: string;
  product_name: string;
  category: string;
  pack_size: string;
  quantity_on_shelf: number;
  availability_status: StockStatus;
  shelf_price_jod: number;
  last_updated: string;
}

export interface StatusSplit { in_stock: number; low_stock: number; out_of_stock: number }
export interface GroupRow extends StatusSplit { total: number; city?: string; category?: string; store_type?: string }

export interface DashboardData {
  filters: { city?: string; category?: string; status?: string };
  as_of: string;
  oldest_update: string;
  dataset_as_of: string;
  options: { cities: string[]; categories: string[]; statuses: StockStatus[] };
  kpis: StatusSplit & {
    listings: number; stores: number; products: number; cities: number;
    in_stock_pct: number; low_stock_pct: number; out_of_stock_pct: number;
  };
  status_split: { status: StockStatus; count: number; pct: number }[];
  by_city: (GroupRow & { city: string })[];
  by_category: (GroupRow & { category: string })[];
  by_store_type: (GroupRow & { store_type: string })[];
  at_risk_products: { product_name: string; category: string; low_stock: number; out_of_stock: number; at_risk: number; listings: number; at_risk_pct: number }[];
  at_risk_stores: { store_name: string; city: string; area: string; low_stock: number; out_of_stock: number; at_risk: number; listings: number }[];
  freshness: { date: string; count: number }[];
}

export interface RecordsData {
  filters: Record<string, string>;
  total: number;
  truncated: boolean;
  records: PosRecord[];
  data_as_of: string;
}

export interface AskQuery {
  filters: Record<string, string>;
  total_matches: number;
  status_counts: Record<StockStatus, number> | null;
  ambiguous: { field: string; term: string; candidates: string[] } | null;
  no_match: Record<string, unknown> | null;
}

export interface AskResponse {
  answer: string;
  records: PosRecord[];
  queries: AskQuery[];
  record_count: number;
  data_as_of: string;
  session_id: string;
  grounded?: boolean;
}

/** Events of the streamed answer (one JSON object per Server-Sent Event); see src/agent/service.py `ask_stream`. */
export type StreamEvent =
  | { type: "start"; session_id: string }
  | { type: "status"; state: "searching" }
  | ({ type: "records" } & Pick<AskResponse, "records" | "queries" | "record_count" | "data_as_of">)
  | { type: "delta"; text: string }
  | { type: "reset" }
  | { type: "replace"; text: string }
  | ({ type: "done" } & AskResponse)
  | { type: "error"; code: string; message: string };
