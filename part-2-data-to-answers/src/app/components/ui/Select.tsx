import React from "react";

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "children"> {
  label?: string;
  options: { value: string; label: string }[];
  emptyLabel?: string;
}

export default function Select({ label, options, emptyLabel, className = "", id, ...rest }: SelectProps) {
  const selectId = id ?? rest.name;
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={selectId} className="text-xs font-semibold uppercase tracking-wide text-text-gray">{label}</label>}
      <select id={selectId} className={`w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-text-dark shadow-sm transition-colors focus:border-brand-blue/40 focus:outline-none focus:ring-1 focus:ring-brand-blue/30 ${className}`} {...rest}>
        {emptyLabel && <option value="">{emptyLabel}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
