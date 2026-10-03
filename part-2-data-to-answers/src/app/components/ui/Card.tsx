import React from "react";

interface CardProps {
  className?: string;
  hover?: boolean;
  padding?: "sm" | "md" | "lg" | "none";
  children: React.ReactNode;
  as?: "div" | "article" | "section" | "li";
}

const paddingStyles = { none: "", sm: "p-4", md: "p-6", lg: "p-8" };

export default function Card({ className = "", hover = false, padding = "md", children, as: Tag = "div" }: CardProps) {
  return <Tag className={`bg-white rounded-2xl shadow-card ${paddingStyles[padding]} ${hover ? "card-hover cursor-default" : ""} ${className}`}>{children}</Tag>;
}
