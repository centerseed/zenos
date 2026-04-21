"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const components: Components = {
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto my-2">
      <table
        className="min-w-full text-xs border-collapse border border-border/60 bg-background/70"
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-foreground/[0.04]" {...props}>
      {children}
    </thead>
  ),
  th: ({ children, ...props }) => (
    <th
      className="border border-border/60 px-3 py-1.5 text-left font-semibold text-foreground"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border border-border/60 px-3 py-1.5 text-foreground align-top" {...props}>
      {children}
    </td>
  ),
  a: ({ children, href, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[color:var(--zen-link,#9a4f2e)] underline underline-offset-2 transition-colors hover:opacity-80"
      {...props}
    >
      {children}
    </a>
  ),
  img: ({ src, alt, ...props }) => (
    <img
      src={src}
      alt={alt ?? ""}
      className="rounded-lg max-w-full max-h-64 object-contain my-2 border border-border"
      loading="lazy"
      {...props}
    />
  ),
  ul: ({ children, ...props }) => (
    <ul className="list-disc list-inside space-y-0.5 my-1" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="list-decimal list-inside space-y-0.5 my-1" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-foreground leading-relaxed" {...props}>
      {children}
    </li>
  ),
  h1: ({ children, ...props }) => (
    <h1 className="text-base font-bold text-foreground mt-3 mb-1" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="text-sm font-semibold text-foreground mt-2.5 mb-1"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3
      className="text-sm font-medium text-foreground mt-2 mb-0.5"
      {...props}
    >
      {children}
    </h3>
  ),
  p: ({ children, ...props }) => (
    <p className="text-foreground leading-relaxed my-1" {...props}>
      {children}
    </p>
  ),
  code: ({ children, className, ...props }) => {
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <pre className="my-2 overflow-x-auto rounded-[2px] border border-border/60 bg-foreground/[0.04] p-3 text-xs text-foreground">
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      );
    }
    return (
      <code
        className="rounded-[2px] border border-border/50 bg-foreground/[0.05] px-1.5 py-0.5 text-[0.8em] font-mono text-foreground"
        {...props}
      >
        {children}
      </code>
    );
  },
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-2 border-l-2 border-border/80 pl-3 text-muted-foreground italic"
      {...props}
    >
      {children}
    </blockquote>
  ),
  hr: (props) => <hr className="border-border my-3" {...props} />,
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-foreground" {...props}>
      {children}
    </strong>
  ),
  em: ({ children, ...props }) => (
    <em className="italic" {...props}>
      {children}
    </em>
  ),
};

/** Extract first image URL from markdown for thumbnail preview */
export function extractFirstImage(markdown: string): string | null {
  const match = markdown.match(/!\[.*?\]\((.*?)\)/);
  return match?.[1] ?? null;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
