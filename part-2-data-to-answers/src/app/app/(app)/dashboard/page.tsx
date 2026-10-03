"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Boxes, CheckCircle2, PackageX, RefreshCw } from "lucide-react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import FilterBar from "@/components/app/FilterBar";
import FreshnessBars from "@/components/app/FreshnessBars";
import KpiCard from "@/components/app/KpiCard";
import { AtRiskProducts, AtRiskStores } from "@/components/app/RiskTables";
import StackedBars from "@/components/app/StackedBars";
import StatusDonut from "@/components/app/StatusDonut";
import { fetchDashboard, type DashboardFilters } from "@/lib/api/availability";
import { formatDate, formatNumber, formatPct } from "@/lib/format";

function Section({ title, subtitle, children, className = "" }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <h2 className="text-base font-bold text-text-dark">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-text-gray">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

export default function DashboardPage() {
  const [filters, setFilters] = useState<DashboardFilters>({});
  const query = useQuery({ queryKey: ["dashboard", filters], queryFn: () => fetchDashboard(filters), placeholderData: (previous) => previous });
  const data = query.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-text-dark">Availability dashboard</h1>
        <p className="text-sm text-text-gray" data-testid="as-of">
          {data ? `Latest recorded POS data as of ${formatDate(data.as_of)}. Oldest record in view: ${formatDate(data.oldest_update)}.` : "Loading the latest recorded POS data."}
        </p>
      </header>

      <Card padding="sm"><FilterBar options={data?.options} value={filters} onChange={setFilters} /></Card>

      {query.isError && !data ? (
        <Card>
          <EmptyState icon={<AlertTriangle className="h-6 w-6" aria-hidden="true" />} title="The dashboard could not load" body={query.error instanceof Error ? query.error.message : "Please try again."}
            action={<Button variant="pill" size="sm" onClick={() => query.refetch()}><RefreshCw className="h-4 w-4" aria-hidden="true" />Try again</Button>} />
        </Card>
      ) : !data ? (
        <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3"><Skeleton className="h-80" /><Skeleton className="h-80 lg:col-span-2" /></div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Listings" value={formatNumber(data.kpis.listings)} hint={`${data.kpis.stores} stores, ${data.kpis.products} products, ${data.kpis.cities} cities`} icon={Boxes} accent="blue" />
            <KpiCard label="In stock" value={formatNumber(data.kpis.in_stock)} hint={formatPct(data.kpis.in_stock_pct)} icon={CheckCircle2} accent="green" />
            <KpiCard label="Low stock" value={formatNumber(data.kpis.low_stock)} hint={formatPct(data.kpis.low_stock_pct)} icon={AlertTriangle} accent="amber" />
            <KpiCard label="Out of stock" value={formatNumber(data.kpis.out_of_stock)} hint={formatPct(data.kpis.out_of_stock_pct)} icon={PackageX} accent="red" />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Section title="Stock status" subtitle="Share of listings by state"><StatusDonut data={data.status_split} /></Section>
            <Section title="Availability by city" subtitle="Listings per city, split by state" className="lg:col-span-2">
              <StackedBars label="Availability by city" data={data.by_city.map((r) => ({ name: r.city, in_stock: r.in_stock, low_stock: r.low_stock, out_of_stock: r.out_of_stock }))} />
            </Section>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Section title="Availability by category" subtitle="Listings per category, split by state">
              <StackedBars label="Availability by category" orientation="horizontal" height={300} data={data.by_category.map((r) => ({ name: r.category, in_stock: r.in_stock, low_stock: r.low_stock, out_of_stock: r.out_of_stock }))} />
            </Section>
            <Section title="Data freshness" subtitle="Listings by the date they were last updated"><FreshnessBars data={data.freshness} /></Section>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Section title="Products to watch" subtitle="Most low or out of stock listings"><AtRiskProducts rows={data.at_risk_products} /></Section>
            <Section title="Stores to watch" subtitle="Stores with the most low or out of stock listings"><AtRiskStores rows={data.at_risk_stores} /></Section>
          </div>
        </>
      )}
    </div>
  );
}
