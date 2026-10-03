import Link from "next/link";
import { Loader2 } from "lucide-react";
import React from "react";

// Variants and sizes follow the Clarity Button: `pill` is the black primary action.
type Variant = "pill" | "pill-white" | "pill-outline" | "primary" | "ghost";
type Size = "sm" | "md" | "lg";

interface ButtonProps {
  variant?: Variant;
  size?: Size;
  href?: string;
  className?: string;
  disabled?: boolean;
  loading?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: () => void;
  children: React.ReactNode;
  "aria-label"?: string;
}

const variantStyles: Record<Variant, string> = {
  pill: "bg-black text-white hover:bg-gray-800 focus-visible:ring-gray-500",
  "pill-white": "bg-white text-black hover:bg-gray-100 focus-visible:ring-white",
  "pill-outline": "border border-black/15 text-text-dark hover:bg-black/[0.04] focus-visible:ring-gray-500",
  primary: "bg-brand-blue text-white hover:bg-brand-purple focus-visible:ring-brand-blue",
  ghost: "text-brand-blue hover:bg-brand-blue/10 focus-visible:ring-brand-blue",
};

const sizeStyles: Record<Size, string> = {
  sm: "px-5 py-2 text-[0.875rem] rounded-full font-medium",
  md: "px-7 py-3 text-[0.9375rem] rounded-full font-medium",
  lg: "px-9 py-3.5 text-base rounded-full font-medium",
};

export default function Button({ variant = "pill", size = "md", href, className = "", disabled = false, loading = false, type = "button", onClick, children, "aria-label": ariaLabel }: ButtonProps) {
  const classes = `inline-flex items-center justify-center gap-2 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`;
  if (href) {
    return <Link href={href} className={classes} aria-label={ariaLabel}>{children}</Link>;
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled || loading} aria-busy={loading || undefined} className={classes} aria-label={ariaLabel}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}
