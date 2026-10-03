import React, { useId } from "react";

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "children"> {
  label?: string;
  options: { value: string; label: string }[];
  emptyLabel?: string;
}

export default function Select({ label, options, emptyLabel, className = "", id, ...rest }: SelectProps) {
  const generated = useId();
  const selectId = id ?? rest.name ?? generated;
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      {label && <label htmlFor={selectId} className="text-xs font-medium text-text-gray">{label}</label>}
      <select id={selectId} className={`h-10 w-full min-w-0 rounded-md border border-[#d0d5dd] bg-white px-3 text-sm text-text-dark transition-colors hover:border-[#9aa3d6] focus-visible:border-brand-blue focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-blue/15 ${className}`} {...rest}>
        {emptyLabel && <option value="">{emptyLabel}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
