// ZenOS · Zen Ink — Radio
// API: Designer spec §2.7
// Keyboard: Arrow keys to move within same name group (via native browser behavior)
"use client";

import React, { useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

export interface RadioProps<T extends string = string> {
  t: ZenInkTokens;
  name: string;
  value: T;
  selected: T;
  onChange: (v: T) => void;
  label?: React.ReactNode;
  disabled?: boolean;
  size?: "sm" | "md";
  id?: string;
  "aria-label"?: string;
}

const sizeMap = {
  sm: { box: 12, inner: 5, gap: 6, fontSize: 11 },
  md: { box: 16, inner: 7, gap: 8, fontSize: 13 },
};

export function Radio<T extends string = string>({
  t,
  name,
  value,
  selected,
  onChange,
  label,
  disabled = false,
  size = "md",
  id,
  "aria-label": ariaLabel,
}: RadioProps<T>) {
  const { c, fontBody } = t;
  const [focused, setFocused] = useState(false);
  const isChecked = value === selected;
  const s = sizeMap[size];

  const focusRing = focused ? `0 0 0 2px ${c.vermLine}` : "none";
  const outerBorder = isChecked ? c.vermillion : focused ? c.vermillion : c.inkHairBold;

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
      {/* Hidden native input — browser handles Arrow key navigation within same name group */}
      <input
        type="radio"
        id={id}
        name={name}
        value={value}
        checked={isChecked}
        disabled={disabled}
        aria-label={!label ? ariaLabel : undefined}
        onChange={() => onChange(value)}
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
      {/* Visual circle */}
      <span
        aria-hidden="true"
        style={{
          flexShrink: 0,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: s.box,
          height: s.box,
          borderRadius: "50%",
          background: c.surfaceHi,
          border: `1px solid ${outerBorder}`,
          boxShadow: focusRing,
          transition: "border-color 0.12s, box-shadow 0.12s",
        }}
      >
        {isChecked && (
          <span
            style={{
              width: s.inner,
              height: s.inner,
              borderRadius: "50%",
              background: c.vermillion,
              transition: "background 0.12s",
            }}
          />
        )}
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
