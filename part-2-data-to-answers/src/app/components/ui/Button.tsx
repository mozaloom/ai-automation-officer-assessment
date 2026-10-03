import Link from "next/link";
import { Loader2 } from "lucide-react";
import React from "react";

// `pill` is the black primary action from Clarity; use it once per view. `outline` and `ghost` are the quiet ones.
type Variant = "pill" | "outline" | "ghost";
type Size = "sm" | "md";

type ButtonProps = {
  variant?: Variant;
  size?: Size;
  href?: string;
  loading?: boolean;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "className"> & { className?: string };

const variantStyles: Record<Variant, string> = {
  pill: "bg-black text-white hover:bg-gray-800 focus-visible:ring-gray-500",
  outline: "border border-black/15 text-text-dark hover:bg-black/[0.04] focus-visible:ring-gray-500",
  ghost: "text-brand-blue hover:bg-brand-blue/10 focus-visible:ring-brand-blue",
};

const sizeStyles: Record<Size, string> = {
  sm: "h-9 px-4 text-sm rounded-full font-medium",
  md: "h-11 px-6 text-[0.9375rem] rounded-full font-medium",
};

export default function Button({ variant = "pill", size = "md", href, className = "", disabled = false, loading = false, type = "button", children, ...rest }: ButtonProps) {
  const classes = `inline-flex select-none items-center justify-center gap-2 whitespace-nowrap transition-[transform,background-color,color] duration-150 ease-[var(--ease-out)] active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`;
  if (href) return <Link href={href} className={classes} aria-label={rest["aria-label"]}>{children}</Link>;
  return (
    <button type={type} disabled={disabled || loading} aria-busy={loading || undefined} className={classes} {...rest}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}
