import React from "react";

interface CardProps {
  className?: string;
  padding?: "sm" | "md" | "none";
  children: React.ReactNode;
}

const paddingStyles = { none: "", sm: "p-4", md: "p-5" };

/** A bordered surface for the few things that need to read as one object (the chat). Everything else uses spacing and hairlines. */
export default function Card({ className = "", padding = "md", children }: CardProps) {
  return <div className={`rounded-xl border border-line bg-white ${paddingStyles[padding]} ${className}`}>{children}</div>;
}
