import type { StockStatus } from "@/lib/api/types";

export const STATUS_COLORS: Record<StockStatus, string> = {
  "In Stock": "#10B981",
  "Low Stock": "#F59E0B",
  "Out of Stock": "#EF4444",
};

export const STATUS_KEYS = ["In Stock", "Low Stock", "Out of Stock"] as const;
