import { apiFetch } from "./client";
import type { DashboardData, RecordsData } from "./types";

export interface DashboardFilters { city?: string; category?: string; status?: string }

export const fetchDashboard = (filters: DashboardFilters = {}) =>
  apiFetch<DashboardData>("/dashboard", { query: { city: filters.city, category: filters.category, status: filters.status } });

export interface RecordsFilters extends DashboardFilters { product?: string; store?: string }

/** The records behind a dashboard row (drill-down). */
export const fetchRecords = (filters: RecordsFilters) =>
  apiFetch<RecordsData>("/records", { query: { city: filters.city, category: filters.category, status: filters.status, product: filters.product, store: filters.store } });
