// ZenOS · Zen Ink — Dropdown (custom popover, multi/single select)
// API: Designer spec §2.4
// Native — no Radix. click-outside, Esc, keyboard navigation (Arrow/Enter)
"use client";

import React, { useState, useRef, useEffect, useCallback, useId } from "react";
import { createPortal } from "react-dom";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { Z } from "./useOverlay";

export interface DropdownItem<T> {
  value: T;
  label: React.ReactNode;
  disabled?: boolean;
}

export interface DropdownProps<T = string> {
  t: ZenInkTokens;
  trigger: React.ReactNode;
  items: DropdownItem<T>[];
  selected?: T[];
  multiple?: boolean;
  onSelect: (next: T[]) => void;
  maxWidth?: number;
  align?: "left" | "right";
  closeOnSelect?: boolean; // default: !multiple
  disabled?: boolean;
  "aria-label"?: string;
}

type Position = { top: number; left: number; width: number };

function DropdownOption<T>({
  item, sel, hl, multiple, onToggle, onHover, t,
}: {
  item: DropdownItem<T>; sel: boolean; hl: boolean; multiple: boolean;
  onToggle: (it: DropdownItem<T>) => void; onHover: () => void;
  t: ZenInkTokens;
}) {
  const { c, fontBody } = t;
  return (
    <li
      role="option"
      aria-selected={sel}
      aria-disabled={item.disabled}
      tabIndex={hl ? 0 : -1}
      onClick={() => onToggle(item)}
      onMouseEnter={onHover}
      style={{
        display: "flex", alignItems: "center", gap: 8, padding: "7px 12px",
        fontFamily: fontBody, fontSize: 13,
        color: item.disabled ? c.inkFaint : sel ? c.ink : c.inkMuted,
        background: hl ? c.paperWarm : "transparent",
        cursor: item.disabled ? "not-allowed" : "pointer",
        outline: "none", transition: "background 0.1s, color 0.1s",
      }}
    >
      {multiple && (
        <span aria-hidden="true" style={{
          flexShrink: 0, width: 12, height: 12, borderRadius: 2,
          border: `1px solid ${sel ? c.ink : c.inkHairBold}`,
          background: sel ? c.ink : "transparent",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
        }}>
          {sel && (
            <svg width={8} height={6} viewBox="0 0 10 8" fill="none">
              <path d="M1 4L3.8 7L9 1" stroke={c.paper} strokeWidth="1.5"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </span>
      )}
      {item.label}
    </li>
  );
}

export function Dropdown<T = string>({
  t, trigger, items, selected = [], multiple = false,
  onSelect, maxWidth = 280, align = "left", closeOnSelect,
  disabled = false, "aria-label": ariaLabel,
}: DropdownProps<T>) {
  const { c, radius } = t;
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState<number>(-1);
  const [mounted, setMounted] = useState(false);
  const [position, setPosition] = useState<Position>({ top: 0, left: 0, width: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listboxId = useId();
  const shouldClose = closeOnSelect !== undefined ? closeOnSelect : !multiple;

  useEffect(() => { setMounted(true); }, []);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const r = triggerRef.current.getBoundingClientRect();
    setPosition({
      top: r.bottom + window.scrollY + 4,
      left: align === "right" ? r.right + window.scrollX - maxWidth : r.left + window.scrollX,
      width: Math.max(r.width, maxWidth),
    });
  }, [align, maxWidth]);

  const handleClose = useCallback(() => {
    setOpen(false); setHighlighted(-1);
    triggerRef.current?.focus();
  }, []);

  const handleOpen = useCallback(() => {
    if (disabled) return;
    updatePosition(); setOpen(true); setHighlighted(-1);
  }, [disabled, updatePosition]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!listRef.current?.contains(e.target as Node) &&
          !triggerRef.current?.contains(e.target as Node)) handleClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); handleClose(); }
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey, true);
    };
  }, [open, handleClose]);

  const toggleItem = useCallback((item: DropdownItem<T>) => {
    if (item.disabled) return;
    if (multiple) {
      const idx = selected.findIndex((s) => s === item.value);
      onSelect(idx >= 0 ? selected.filter((_, i) => i !== idx) : [...selected, item.value]);
    } else {
      onSelect([item.value]);
    }
    if (shouldClose) handleClose();
  }, [multiple, onSelect, selected, shouldClose, handleClose]);

  useEffect(() => {
    if (highlighted >= 0 && listRef.current) {
      listRef.current.querySelectorAll<HTMLElement>("[role='option']")[highlighted]?.focus();
    }
  }, [highlighted]);

  const popover = open && mounted && (
    <ul ref={listRef} id={listboxId} role="listbox" aria-label={ariaLabel}
      aria-multiselectable={multiple}
      onKeyDown={(e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setHighlighted((h) => Math.min(items.length - 1, h + 1)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setHighlighted((h) => Math.max(0, h - 1)); }
        else if (e.key === "Enter" && highlighted >= 0) { e.preventDefault(); toggleItem(items[highlighted]); }
      }}
      style={{
        position: "absolute", top: position.top, left: position.left, width: position.width,
        maxWidth, maxHeight: 320, overflowY: "auto", zIndex: Z.tooltip,
        background: c.surfaceHi, border: `1px solid ${c.inkHair}`, borderRadius: radius,
        boxShadow: "0 8px 24px rgba(58, 52, 44, 0.12)", margin: 0, padding: "4px 0", listStyle: "none",
      }}
    >
      {items.map((item, idx) => (
        <DropdownOption key={idx} item={item} sel={selected.includes(item.value)}
          hl={idx === highlighted} multiple={multiple} t={t}
          onToggle={toggleItem} onHover={() => setHighlighted(idx)} />
      ))}
    </ul>
  );

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <div ref={triggerRef} role="button" aria-haspopup="listbox" aria-expanded={open}
        aria-controls={open ? listboxId : undefined} aria-disabled={disabled}
        tabIndex={disabled ? -1 : 0}
        onClick={open ? handleClose : handleOpen}
        onKeyDown={(e) => {
          if (["Enter", " ", "ArrowDown"].includes(e.key)) {
            e.preventDefault(); if (!open) handleOpen(); else setHighlighted(0);
          } else if (e.key === "ArrowUp" && open) {
            e.preventDefault(); setHighlighted((h) => Math.max(0, h - 1));
          }
        }}
        style={{ display: "inline-block" }}
      >
        {trigger}
      </div>
      {popover && createPortal(popover, document.body)}
    </div>
  );
}
