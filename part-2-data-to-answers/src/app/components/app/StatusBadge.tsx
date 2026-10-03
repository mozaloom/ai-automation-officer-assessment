import Badge from "@/components/ui/Badge";
import { statusVariant } from "@/lib/format";
import type { StockStatus } from "@/lib/api/types";

export default function StatusBadge({ status }: { status: StockStatus }) {
  return <Badge variant={statusVariant(status)} className="whitespace-nowrap">{status}</Badge>;
}
