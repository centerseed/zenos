// ZenOS · Zen Ink — Input
// API: Designer spec §2.1
"use client";

import React, { useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

type InputSize = "sm" | "md";

export interface InputProps {
  t: ZenInkTokens;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "email" | "date" | "number" | "password";
  disabled?: boolean;
  autoFocus?: boolean;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onBlur?: () => void;
  size?: InputSize;
  invalid?: boolean;
  style?: React.CSSProperties;
  "aria-label"?: string;
  id?: string;
  name?: string;
}

const sizeMap: Record<InputSize, { padding: string; fontSize: number }> = {
  sm: { padding: "6px 10px", fontSize: 12 },
  md: { padding: "9px 12px", fontSize: 13 },
};

export function Input({
  t,
  value,
  onChange,
  placeholder,
  type = "text",
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
}: InputProps) {
  const { c, fontBody, radius } = t;
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

  const focusRing = focused
    ? `0 0 0 2px ${c.vermLine}`
    : "none";

  return (
    <input
      id={id}
      name={name}
      type={type}
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
      aria-label={ariaLabel}
      aria-invalid={invalid || undefined}
      style={{
        display: "block",
        width: "100%",
        boxSizing: "border-box",
        padding: s.padding,
        fontSize: s.fontSize,
        fontFamily: fontBody,
        fontWeight: 400,
        lineHeight: 1.5,
        color: disabled ? c.inkFaint : c.ink,
        background: disabled ? c.paperWarm : c.surfaceHi,
        border: `1px solid ${borderColor}`,
        borderRadius: radius,
        outline: "none",
        boxShadow: focusRing,
        cursor: disabled ? "not-allowed" : "text",
        opacity: disabled ? 0.6 : 1,
        transition: "border-color 0.15s, box-shadow 0.15s",
        ...style,
      }}
    />
  );
}
