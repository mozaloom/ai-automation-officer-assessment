import React, { useId } from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leadingIcon?: React.ReactNode;
  trailing?: React.ReactNode;
}

export default function Input({ label, error, hint, leadingIcon, trailing, className = "", id, ...rest }: InputProps) {
  const generated = useId();
  const inputId = id ?? rest.name ?? generated;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  const pad = `${leadingIcon ? "ps-10" : "ps-3.5"} ${trailing ? "pe-11" : "pe-3.5"}`;
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={inputId} className="text-sm font-medium text-text-dark">{label}</label>}
      <div className="group relative">
        {leadingIcon && <span className="pointer-events-none absolute inset-y-0 start-0 flex items-center ps-3 text-text-light transition-colors group-focus-within:text-brand-blue">{leadingIcon}</span>}
        <input id={inputId} aria-invalid={error ? true : undefined} aria-describedby={describedBy}
          className={`h-11 w-full rounded-md border bg-white text-sm text-text-dark placeholder:text-text-light outline-none transition-colors hover:border-[#9aa3d6] focus-visible:border-brand-blue focus-visible:ring-4 focus-visible:ring-brand-blue/15 ${error ? "border-red-400" : "border-[#d0d5dd]"} ${pad} ${className}`} {...rest} />
        {trailing && <span className="absolute inset-y-0 end-0 flex items-center pe-1.5">{trailing}</span>}
      </div>
      {hint && !error && <p id={`${inputId}-hint`} className="text-xs text-text-gray">{hint}</p>}
      {error && <p id={`${inputId}-error`} className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
