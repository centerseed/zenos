// ZenOS · Zen Ink — Button
// Supports variant: "ink" | "outline" | "ghost" | "seal"
// Supports size: "sm" | "md" | "lg"
// Ported 1:1 from design-ref/components.jsx
"use client";

import React, { useState } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { Icon } from "./Icons";

type BtnVariant = "ink" | "outline" | "ghost" | "seal";
type BtnSize = "sm" | "md" | "lg";

interface BtnProps {
  children?: React.ReactNode;
  t: ZenInkTokens;
  variant?: BtnVariant;
  icon?: string | React.ReactNode;
  onClick?: () => void;
  size?: BtnSize;
  style?: React.CSSProperties;
}

const sizeMap: Record<BtnSize, { p: string; fs: number; ic: number }> = {
  sm: { p: "4px 10px", fs: 11, ic: 12 },
  md: { p: "7px 14px", fs: 12, ic: 13 },
  lg: { p: "10px 20px", fs: 13, ic: 14 },
};

export function Btn({
  children,
  t,
  variant = "ghost",
  icon,
  onClick,
  size = "md",
  style,
}: BtnProps) {
  const { c, fontBody, radius } = t;
  const [hv, setHv] = useState(false);
  const s = sizeMap[size];

  const variants: Record<BtnVariant, { bg: string; fg: string; bd: string }> = {
    ink: { bg: hv ? c.inkSoft : c.ink, fg: c.paper, bd: "transparent" },
    outline: {
      bg: hv ? c.surfaceHi : "transparent",
      fg: c.ink,
      bd: c.inkHairBold,
    },
    ghost: {
      bg: hv ? c.surface : "transparent",
      fg: hv ? c.ink : c.inkMuted,
      bd: c.inkHair,
    },
    seal: {
      bg: hv ? c.seal : c.vermillion,
      fg: c.sealInk,
      bd: "transparent",
    },
  };
  const V = variants[variant];

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHv(true)}
      onMouseLeave={() => setHv(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: s.p,
        fontSize: s.fs,
        fontFamily: fontBody,
        fontWeight: 500,
        letterSpacing: "0.02em",
        background: V.bg,
        color: V.fg,
        border: `1px solid ${V.bd}`,
        borderRadius: radius,
        cursor: "pointer",
        transition: "all .15s",
        ...style,
      }}
    >
      {icon && <Icon d={icon} size={s.ic} />}
      {children}
    </button>
  );
}
