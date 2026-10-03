import React from "react";

export default function EmptyState({ title, body, action, icon }: { title: string; body?: string; action?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      {icon && <div className="mb-2 rounded-2xl bg-brand-blue/[0.08] p-4 text-brand-blue">{icon}</div>}
      <h3 className="text-lg font-semibold text-text-dark">{title}</h3>
      {body && <p className="max-w-sm text-sm text-text-gray">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
