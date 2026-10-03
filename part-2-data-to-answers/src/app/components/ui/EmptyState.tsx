import React from "react";

export default function EmptyState({ title, body, action, icon }: { title: string; body?: string; action?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      {icon && <div className="text-text-light">{icon}</div>}
      <h3 className="text-base font-semibold text-text-dark">{title}</h3>
      {body && <p className="max-w-sm text-sm text-text-gray">{body}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
