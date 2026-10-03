import React from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leadingIcon?: React.ReactNode;
  trailing?: React.ReactNode;
  labelClassName?: string;
}

export default function Input({ label, error, hint, leadingIcon, trailing, labelClassName, className = "", id, ...rest }: InputProps) {
  const inputId = id ?? rest.name;
  const pad = `${leadingIcon ? "ps-11" : "ps-4"} ${trailing ? "pe-11" : "pe-4"}`;
  const errorCls = error ? "border-red-400 focus:border-red-500 focus:ring-red-500/30" : "";
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={inputId} className={labelClassName ?? "text-sm font-medium text-text-dark"}>{label}</label>}
      <div className="group relative">
        {leadingIcon && <span className="pointer-events-none absolute inset-y-0 start-0 flex items-center ps-3.5 text-text-light transition-colors group-focus-within:text-brand-blue">{leadingIcon}</span>}
        <input id={inputId} aria-invalid={error ? true : undefined} className={`w-full rounded-xl border border-gray-200 bg-white py-3 text-sm text-text-dark placeholder:text-text-light shadow-sm outline-none transition focus:border-brand-blue/40 focus:ring-1 focus:ring-brand-blue/30 ${pad} ${errorCls} ${className}`} {...rest} />
        {trailing && <span className="absolute inset-y-0 end-0 flex items-center pe-2">{trailing}</span>}
      </div>
      {hint && !error && <p className="text-xs text-text-gray">{hint}</p>}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
