"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders the assistant's answer (markdown) with the same type scale as the rest of the app. */
export default function AnswerMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 ps-5 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 ps-5 last:mb-0">{children}</ol>,
        strong: ({ children }) => <strong className="font-semibold text-text-dark">{children}</strong>,
        h1: ({ children }) => <p className="mb-1 font-semibold">{children}</p>,
        h2: ({ children }) => <p className="mb-1 font-semibold">{children}</p>,
        h3: ({ children }) => <p className="mb-1 font-semibold">{children}</p>,
        table: ({ children }) => <div className="my-3 overflow-x-auto"><table className="w-full min-w-max text-sm">{children}</table></div>,
        thead: ({ children }) => <thead className="border-b border-line">{children}</thead>,
        tbody: ({ children }) => <tbody className="divide-y divide-line">{children}</tbody>,
        th: ({ children }) => <th className="py-2 pe-4 text-start text-xs font-medium text-text-gray">{children}</th>,
        td: ({ children }) => <td className="py-2 pe-4 text-start tabular-nums">{children}</td>,
        a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-blue underline underline-offset-2">{children}</a>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
