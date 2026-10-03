"use client";

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import Skeleton from "@/components/ui/Skeleton";
import { fetchRecords, type RecordsFilters } from "@/lib/api/availability";
import { describeError } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n/I18nProvider";
import RecordsTable from "./RecordsTable";

export interface Drill { title: string; filters: RecordsFilters }

/** A side panel with the records behind a dashboard row. Native <dialog>: Escape closes it and focus returns to where it came from. */
export default function DrillPanel({ drill, onClose }: { drill: Drill | null; onClose: () => void }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const query = useQuery({ queryKey: ["records", drill?.filters], queryFn: () => fetchRecords(drill!.filters), enabled: drill !== null });

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (drill && !dialog.open) dialog.showModal();
    if (!drill && dialog.open) dialog.close();
  }, [drill]);

  const data = query.data;
  return (
    <dialog ref={ref} aria-label={drill?.title ?? t.dashboard.interactive.recordsTitle} onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}
      className="m-0 ms-auto h-dvh max-h-none w-full max-w-4xl bg-white p-0 text-text-dark shadow-xl backdrop:bg-black/40">
      {drill && (
        <div className="flex h-full flex-col">
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <p className="text-xs text-text-gray">{t.dashboard.interactive.recordsTitle}</p>
              <h2 className="truncate text-lg font-semibold">{drill.title}</h2>
            </div>
            <button type="button" onClick={onClose} aria-label={t.common.close} className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-wash active:scale-[0.97]"><X className="h-4 w-4" aria-hidden="true" /></button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
            {query.isError ? <p role="alert" className="text-sm text-red-700">{t.dashboard.interactive.loadError} {describeError(query.error, t)}</p>
              : !data ? <div aria-busy="true"><Skeleton className="h-64" /></div>
              : (
                <>
                  <RecordsTable records={data.records} total={data.total} asOf={data.data_as_of} collapsible={false} limit={data.records.length} />
                  {data.truncated && <p className="mt-3 text-xs text-text-gray">{t.dashboard.interactive.truncated(data.records.length)}</p>}
                </>
              )}
          </div>
        </div>
      )}
    </dialog>
  );
}
