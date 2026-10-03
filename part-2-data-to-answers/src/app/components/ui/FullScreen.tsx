"use client";

import { useRef, useState } from "react";
import { Maximize2, X } from "lucide-react";
import { useI18n } from "@/lib/i18n/I18nProvider";

/**
 * A button that shows `children` in a full-screen dialog. Uses the native <dialog>, so Escape closes it,
 * focus stays inside while it is open and returns to the button afterwards. The content is only mounted while open.
 */
export default function FullScreen({ title, children }: { title: string; children: React.ReactNode }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => { setOpen(true); ref.current?.showModal(); }} aria-label={`${t.common.fullScreen}: ${title}`} title={t.common.fullScreen}
        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-text-gray transition-colors hover:bg-wash hover:text-text-dark active:scale-[0.97]">
        <Maximize2 className="h-4 w-4" aria-hidden="true" />
      </button>
      <dialog ref={ref} aria-label={title} onClose={() => setOpen(false)} className="m-0 h-dvh max-h-none w-screen max-w-none bg-white p-0 text-text-dark backdrop:bg-black/40">
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-line px-4 py-3 sm:px-8">
            <h2 className="text-base font-semibold">{title}</h2>
            <button type="button" onClick={() => ref.current?.close()} aria-label={t.common.close} className="inline-flex h-9 items-center gap-2 rounded-full border border-black/15 px-4 text-sm transition-colors hover:bg-black/[0.04] active:scale-[0.97]">
              <X className="h-4 w-4" aria-hidden="true" />{t.common.close}
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-4 py-6 sm:px-8">{open && children}</div>
        </div>
      </dialog>
    </>
  );
}
