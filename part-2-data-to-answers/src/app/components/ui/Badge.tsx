import React from "react";

type Variant = "lavender" | "blue" | "purple" | "green" | "amber" | "red" | "gray";

const variantStyles: Record<Variant, string> = {
  lavender: "bg-brand-lavender text-white",
  blue: "bg-brand-blue text-white",
  purple: "bg-brand-purple text-white",
  green: "bg-emerald-500 text-white",
  amber: "bg-amber-500 text-white",
  red: "bg-red-500 text-white",
  gray: "bg-gray-100 text-gray-700",
};

export default function Badge({ variant = "lavender", className = "", children }: { variant?: Variant; className?: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center justify-center px-3 py-1 text-xs font-bold rounded-full tracking-wide uppercase ${variantStyles[variant]} ${className}`}>{children}</span>;
}
