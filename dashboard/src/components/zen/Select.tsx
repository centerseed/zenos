// ZenOS · Zen Ink — Select (native <select>)
// API: Designer spec §2.3
"use client";

import React, { useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

export interface SelectOption {
  value: string;
  label: string;
  tone?: "plain" | "accent" | "jade" | "ocher" | "muted";
}

export interface SelectProps {
  t: ZenInkTokens;
  value: string | null;
  onChange: (v: string | null) => void;
  options: SelectOption[];
  placeholder?: string;
  size?: "sm" | "md";
  clearable?: boolean;
  disabled?: boolean;
  "aria-label"?: string;
  id?: string;
  name?: string;
  invalid?: boolean;
  style?: React.CSSProperties;
}

const sizeMap = {
  sm: { padding: "6px 28px 6px 10px", fontSize: 12 },
  md: { padding: "9px 28px 9px 12px", fontSize: 13 },
};

export function Select({
  t,
  value,
  onChange,
  options,
  placeholder,
  size = "md",
  clearable = false,
  disabled = false,
  "aria-label": ariaLabel,
  id,
  name,
  invalid = false,
  style,
}: SelectProps) {
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

  const focusRing = focused ? `0 0 0 2px ${c.vermLine}` : "none";

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value;
    onChange(v === "" ? null : v);
  };

  return (
    <div style={{ position: "relative", display: "inline-block", width: "100%", ...style }}>
      <select
        id={id}
        name={name}
        value={value ?? ""}
        onChange={handleChange}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-invalid={invalid || undefined}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          display: "block",
          width: "100%",
          boxSizing: "border-box",
          padding: s.padding,
          fontSize: s.fontSize,
          fontFamily: fontBody,
          fontWeight: 400,
          lineHeight: 1.5,
          color: value === null ? c.inkFaint : disabled ? c.inkFaint : c.ink,
          background: disabled ? c.paperWarm : c.surfaceHi,
          border: `1px solid ${borderColor}`,
          borderRadius: radius,
          outline: "none",
          boxShadow: focusRing,
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          appearance: "none",
          WebkitAppearance: "none",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
      >
        {placeholder && (
          <option value="" disabled={!clearable}>
            {placeholder}
          </option>
        )}
        {clearable && value !== null && (
          <option value="">— 清除 —</option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {/* Custom arrow */}
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          right: 10,
          top: "50%",
          transform: "translateY(-50%)",
          pointerEvents: "none",
          color: disabled ? c.inkFaint : c.inkMuted,
          fontSize: 10,
          lineHeight: 1,
        }}
      >
        ▾
      </span>
    </div>
  );
}
