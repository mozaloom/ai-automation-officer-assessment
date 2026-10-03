"use client";

import { Suspense, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import FullScreen from "@/components/ui/FullScreen";
import Skeleton from "@/components/ui/Skeleton";
import { fetchDashboard, type DashboardFilters } from "@/lib/api/availability";
import { describeError } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n/I18nProvider";
import DrillPanel, { type Drill } from "./DrillPanel";
import FilterBar from "./FilterBar";
import FreshnessStrip from "./FreshnessStrip";
import KpiStrip from "./KpiStrip";
import StateBars from "./StateBars";
import StockShareBar from "./StockShareBar";
import { WatchProducts, WatchStores, type DrillTarget } from "./WatchTables";

function Section({ id, title, subtitle, children }: { id: string; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="min-w-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 id={id} className="text-sm font-semibold text-text-dark">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-text-gray">{subtitle}</p>}
        </div>
        <FullScreen title={title}><div className="mx-auto max-w-5xl">{children}</div></FullScreen>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Dashboard() {
  const { t, date, label } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  // The filters live in the URL, so a filtered view can be shared, bookmarked and reloaded.
  const filters = useMemo<DashboardFilters>(() => ({ city: params.get("city") ?? undefined, category: params.get("category") ?? undefined, status: params.get("status") ?? undefined }), [params]);
  const setFilters = (next: DashboardFilters) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(next)) if (value) query.set(key, value);
    const qs = query.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const [drill, setDrill] = useState<Drill | null>(null);
  const toggle = (key: keyof DashboardFilters, value: string) => setFilters({ ...filters, [key]: filters[key] === value ? undefined : value });
  const openDrill = (target: DrillTarget) => setDrill({ title: target.title, filters: { ...filters, product: target.product, store: target.store } });
  const active = Boolean(filters.city || filters.category || filters.status);
  const query = useQuery({ queryKey: ["dashboard", filters], queryFn: () => fetchDashboard(filters), placeholderData: (previous) => previous });
  const data = query.data;
  const rowsOf = <K extends "city" | "category">(rows: (Record<K, string> & { in_stock: number; low_stock: number; out_of_stock: number })[], key: K) =>
    rows.map((r) => ({ value: r[key], name: label(key, r[key]), in_stock: r.in_stock, low_stock: r.low_stock, out_of_stock: r.out_of_stock }));

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-text-dark">{t.dashboard.title}</h1>
        <p className="mt-1 text-sm text-text-gray" data-testid="as-of">{data ? t.dashboard.asOf(date(data.as_of), date(data.oldest_update)) : t.dashboard.loadingAsOf}</p>
      </header>

      <div className="space-y-2">
        <FilterBar options={data?.options} value={filters} onChange={setFilters} />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-gray">
          <span>{t.dashboard.interactive.hint}</span>
          {active && <button type="button" onClick={() => setDrill({ title: t.dashboard.interactive.recordsTitle, filters })} className="font-medium text-brand-blue underline-offset-4 hover:underline">{t.dashboard.interactive.viewRecords}</button>}
        </div>
      </div>

      {query.isError && !data ? (
        <EmptyState icon={<AlertTriangle className="h-6 w-6" aria-hidden="true" />} title={t.dashboard.errorTitle} body={describeError(query.error, t)}
          action={<Button variant="outline" size="sm" onClick={() => query.refetch()}><RefreshCw className="h-4 w-4" aria-hidden="true" />{t.dashboard.retry}</Button>} />
      ) : !data ? (
        <div className="space-y-8" aria-busy="true" aria-label={t.dashboard.loadingLabel}>
          <Skeleton className="h-28" />
          <div className="grid gap-8 lg:grid-cols-2"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>
          <div className="grid gap-8 lg:grid-cols-2"><Skeleton className="h-72" /><Skeleton className="h-72" /></div>
        </div>
      ) : (
        <>
          <KpiStrip kpis={data.kpis} />
          <div className="grid gap-x-12 gap-y-8 lg:grid-cols-2">
            <Section id="share" title={t.dashboard.share.title} subtitle={t.dashboard.share.subtitle}><StockShareBar data={data.status_split} selected={filters.status} onSelect={(s) => toggle("status", s)} /></Section>
            <Section id="freshness" title={t.dashboard.freshness.title} subtitle={t.dashboard.freshness.subtitle}><FreshnessStrip data={data.freshness} /></Section>
          </div>
          <div className="grid gap-x-12 gap-y-8 border-t border-line pt-8 lg:grid-cols-2">
            <Section id="by-city" title={t.dashboard.byCity.title} subtitle={t.dashboard.byCity.subtitle}><StateBars rows={rowsOf(data.by_city, "city")} selected={filters.city} onSelect={(v) => toggle("city", v)} /></Section>
            <Section id="by-category" title={t.dashboard.byCategory.title} subtitle={t.dashboard.byCategory.subtitle}><StateBars rows={rowsOf(data.by_category, "category")} selected={filters.category} onSelect={(v) => toggle("category", v)} /></Section>
          </div>
          <div className="grid gap-x-12 gap-y-8 border-t border-line pt-8 lg:grid-cols-2">
            <Section id="watch-products" title={t.dashboard.watchProducts.title} subtitle={t.dashboard.watchProducts.subtitle}><WatchProducts rows={data.at_risk_products} onDrill={openDrill} /></Section>
            <Section id="watch-stores" title={t.dashboard.watchStores.title} subtitle={t.dashboard.watchStores.subtitle}><WatchStores rows={data.at_risk_stores} onDrill={openDrill} /></Section>
          </div>
        </>
      )}
      <DrillPanel drill={drill} onClose={() => setDrill(null)} />
    </div>
  );
}

export default function DashboardView() {
  return <Suspense fallback={null}><Dashboard /></Suspense>;
}
