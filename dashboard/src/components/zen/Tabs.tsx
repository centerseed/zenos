// ZenOS · Zen Ink — Tabs
// API: Designer spec §2.8
// ARIA: role=tablist / role=tab / role=tabpanel / aria-selected / aria-controls
// Keyboard: Arrow Left/Right to navigate tabs
"use client";

import React, { useId, useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

type TabsVariant = "underline" | "segment";

export interface TabItem<T extends string> {
  value: T;
  label: React.ReactNode;
  disabled?: boolean;
}

export interface TabsProps<T extends string> {
  t: ZenInkTokens;
  value: T;
  onChange: (v: T) => void;
  items: TabItem<T>[];
  variant?: TabsVariant;
  /** If provided, renders the active tab panel inline */
  panels?: Partial<Record<T, React.ReactNode>>;
}

export function Tabs<T extends string>({
  t,
  value,
  onChange,
  items,
  variant = "underline",
  panels,
}: TabsProps<T>) {
  const { c, fontHead, fontBody, radius } = t;
  const baseId = useId();
  const [focusedIdx, setFocusedIdx] = useState<number>(-1);

  const tabId = (v: T) => `${baseId}-tab-${v}`;
  const panelId = (v: T) => `${baseId}-panel-${v}`;

  const handleKeyDown = (e: React.KeyboardEvent, idx: number) => {
    const enabledItems = items.filter((it) => !it.disabled);
    const enabledIdx = enabledItems.findIndex((it) => it.value === items[idx].value);

    if (e.key === "ArrowRight") {
      e.preventDefault();
      const next = enabledItems[(enabledIdx + 1) % enabledItems.length];
      if (next) onChange(next.value);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      const prev = enabledItems[(enabledIdx - 1 + enabledItems.length) % enabledItems.length];
      if (prev) onChange(prev.value);
    } else if (e.key === "Home") {
      e.preventDefault();
      const first = enabledItems[0];
      if (first) onChange(first.value);
    } else if (e.key === "End") {
      e.preventDefault();
      const last = enabledItems[enabledItems.length - 1];
      if (last) onChange(last.value);
    }
  };

  const isUnderline = variant === "underline";
  const isSegment = variant === "segment";

  return (
    <div>
      <div
        role="tablist"
        style={{
          display: "flex",
          gap: isSegment ? 2 : 0,
          background: isSegment ? c.paperWarm : "transparent",
          borderRadius: isSegment ? radius : 0,
          borderBottom: isUnderline ? `1px solid ${c.inkHair}` : undefined,
          padding: isSegment ? 3 : 0,
        }}
      >
        {items.map((item, idx) => {
          const isActive = item.value === value;
          const isDisabled = item.disabled;

          let tabStyle: React.CSSProperties = {
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: isSegment ? "5px 14px" : "8px 16px",
            fontFamily: fontHead,
            fontSize: 13,
            fontWeight: isActive ? 500 : 400,
            letterSpacing: "0.02em",
            cursor: isDisabled ? "not-allowed" : "pointer",
            opacity: isDisabled ? 0.4 : 1,
            outline: "none",
            border: "none",
            background: "transparent",
            color: isActive ? c.ink : c.inkMuted,
            borderRadius: isSegment ? radius : 0,
            transition: "color 0.15s, background 0.15s",
            position: "relative",
          };

          if (isSegment && isActive) {
            tabStyle = {
              ...tabStyle,
              background: c.surfaceHi,
              boxShadow: `0 1px 3px rgba(20, 18, 16, 0.08)`,
            };
          }

          if (isUnderline && isActive) {
            tabStyle = {
              ...tabStyle,
              color: c.vermillion,
            };
          }

          return (
            <button
              key={item.value}
              id={tabId(item.value)}
              role="tab"
              aria-selected={isActive}
              aria-controls={panelId(item.value)}
              aria-disabled={isDisabled}
              tabIndex={isActive ? 0 : -1}
              disabled={isDisabled}
              onClick={() => !isDisabled && onChange(item.value)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              onFocus={() => setFocusedIdx(idx)}
              onBlur={() => setFocusedIdx(-1)}
              style={{
                ...tabStyle,
                // Underline indicator via pseudo-via inline approach using pseudo-border-bottom
                ...(isUnderline
                  ? {
                      paddingBottom: isActive ? 6 : 7,
                      borderBottom: isActive
                        ? `2px solid ${c.vermillion}`
                        : "2px solid transparent",
                    }
                  : {}),
              }}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      {/* Panels */}
      {panels &&
        items.map((item) => (
          <div
            key={item.value}
            id={panelId(item.value)}
            role="tabpanel"
            aria-labelledby={tabId(item.value)}
            hidden={item.value !== value}
            style={{ paddingTop: 16 }}
          >
            {panels[item.value]}
          </div>
        ))}
    </div>
  );
}
