// ZenOS · Zen Ink — Textarea
// API: Designer spec §2.2
"use client";

import React, { useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

type TextareaSize = "sm" | "md";

export interface TextareaProps {
  t: ZenInkTokens;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onBlur?: () => void;
  size?: TextareaSize;
  invalid?: boolean;
  style?: React.CSSProperties;
  "aria-label"?: string;
  id?: string;
  name?: string;
  rows?: number;
  resize?: "none" | "vertical";
  fontVariant?: "body" | "mono";
}

const sizeMap: Record<TextareaSize, { padding: string; fontSize: number }> = {
  sm: { padding: "6px 10px", fontSize: 12 },
  md: { padding: "9px 12px", fontSize: 13 },
};

export function Textarea({
  t,
  value,
  onChange,
  placeholder,
  disabled = false,
  autoFocus = false,
  onKeyDown,
  onBlur,
  size = "md",
  invalid = false,
  style,
  "aria-label": ariaLabel,
  id,
  name,
  rows = 4,
  resize = "vertical",
  fontVariant = "body",
}: TextareaProps) {
  const { c, fontBody, fontMono, radius } = t;
  const [focused, setFocused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const s = sizeMap[size];

  const borderColor = invalid
    ? c.vermillion
    : focused
    ? c.vermillion
    : hovered
    ? c.inkHairBold
    : c.inkHair;

  const focusRing = focused ? `0 0 0 2px ${c.vermLine}` : "none";
  const fontFamily = fontVariant === "mono" ? fontMono : fontBody;

  return (
    <textarea
      id={id}
      name={name}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      autoFocus={autoFocus}
      onKeyDown={onKeyDown}
      onBlur={() => {
        setFocused(false);
        onBlur?.();
      }}
      onFocus={() => setFocused(true)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      rows={rows}
      aria-label={ariaLabel}
      aria-invalid={invalid || undefined}
      style={{
        display: "block",
        width: "100%",
        boxSizing: "border-box",
        padding: s.padding,
        fontSize: s.fontSize,
        fontFamily,
        fontWeight: 400,
        lineHeight: 1.6,
        color: disabled ? c.inkFaint : c.ink,
        background: disabled ? c.paperWarm : c.surfaceHi,
        border: `1px solid ${borderColor}`,
        borderRadius: radius,
        outline: "none",
        boxShadow: focusRing,
        cursor: disabled ? "not-allowed" : "text",
        opacity: disabled ? 0.6 : 1,
        resize,
        transition: "border-color 0.15s, box-shadow 0.15s",
        ...style,
      }}
    />
  );
}
