// ZenOS · Zen Ink — Checkbox
// API: Designer spec §2.7
// Keyboard: Space to toggle
"use client";

import React, { useRef, useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

export interface CheckboxProps {
  t: ZenInkTokens;
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: React.ReactNode;
  disabled?: boolean;
  size?: "sm" | "md";
  id?: string;
  name?: string;
  "aria-label"?: string;
}

const sizeMap = {
  sm: { box: 12, gap: 6, fontSize: 11 },
  md: { box: 16, gap: 8, fontSize: 13 },
};

export function Checkbox({
  t,
  checked,
  onChange,
  label,
  disabled = false,
  size = "md",
  id,
  name,
  "aria-label": ariaLabel,
}: CheckboxProps) {
  const { c, fontBody, radius } = t;
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const s = sizeMap[size];

  const boxBorder = checked
    ? "transparent"
    : focused
    ? c.vermillion
    : c.inkHairBold;

  const focusRing = focused ? `0 0 0 2px ${c.vermLine}` : "none";

  return (
    <label
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: s.gap,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        fontFamily: fontBody,
        fontSize: s.fontSize,
        color: c.ink,
        userSelect: "none",
      }}
    >
      {/* Hidden native input for a11y */}
      <input
        ref={inputRef}
        type="checkbox"
        id={id}
        name={name}
        checked={checked}
        disabled={disabled}
        aria-label={!label ? ariaLabel : undefined}
        onChange={(e) => onChange(e.target.checked)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          position: "absolute",
          opacity: 0,
          width: s.box,
          height: s.box,
          margin: 0,
          cursor: "inherit",
        }}
      />
      {/* Visual box */}
      <span
        aria-hidden="true"
        style={{
          flexShrink: 0,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: s.box,
          height: s.box,
          borderRadius: radius,
          background: checked ? c.ink : c.surfaceHi,
          border: `1px solid ${boxBorder}`,
          boxShadow: focusRing,
          transition: "background 0.12s, border-color 0.12s, box-shadow 0.12s",
        }}
      >
        {checked && (
          <svg
            width={s.box * 0.65}
            height={s.box * 0.5}
            viewBox="0 0 10 8"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M1 4L3.8 7L9 1"
              stroke={c.paper}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
