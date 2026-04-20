"use client";

import React, { useMemo } from "react";
import { useInk } from "@/lib/zen-ink/tokens";

export interface HeadingItem {
  level: number;
  text: string;
  id: string;
}

interface DocOutlineProps {
  content: string;
  /** Optional active heading id for highlight */
  activeId?: string;
}

/**
 * Parses markdown headings from raw content using a lightweight regex pass.
 * Supports #, ##, ### (H1–H3).
 * Generates a slug-style id from heading text (matches GFM github spec).
 */
export function parseHeadings(content: string): HeadingItem[] {
  const lines = content.split("\n");
  const items: HeadingItem[] = [];

  for (const line of lines) {
    const match = line.match(/^(#{1,3})\s+(.+)$/);
    if (!match) continue;
    const level = match[1].length;
    const text = match[2].trim();
    // slug: lowercase, replace non-alphanumeric with hyphen, collapse hyphens
    const id = text
      .toLowerCase()
      .replace(/[^\w\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
    items.push({ level, text, id });
  }

  return items;
}

export function DocOutline({ content, activeId }: DocOutlineProps) {
  const t = useInk();
  const { c, fontMono, fontBody } = t;

  const headings = useMemo(() => parseHeadings(content), [content]);

  if (headings.length === 0) {
    return (
      <div style={{ fontSize: 11, color: c.inkFaint, padding: "6px 0", fontFamily: fontBody }}>
        無大綱
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {headings.map((h, i) => {
        const isActive = h.id === activeId;
        const indent = (h.level - 1) * 12;

        return (
          <a
            key={`${h.id}-${i}`}
            href={`#${h.id}`}
            data-testid="outline-item"
            data-heading-id={h.id}
            style={{
              display: "block",
              paddingLeft: indent + 8,
              paddingTop: 5,
              paddingBottom: 5,
              paddingRight: 8,
              fontSize: h.level === 1 ? 12.5 : h.level === 2 ? 12 : 11.5,
              fontFamily: fontBody,
              color: isActive ? c.ink : c.inkMuted,
              fontWeight: isActive || h.level === 1 ? 500 : 400,
              borderLeft: isActive ? `2px solid ${c.vermillion}` : "2px solid transparent",
              textDecoration: "none",
              lineHeight: 1.4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              cursor: "pointer",
              transition: "color 0.1s",
            }}
          >
            {h.text}
          </a>
        );
      })}
    </div>
  );
}
