// ZenOS · Zen Ink — Panel (minimal Card replacement)
// API: Designer spec §2.9
// Guidance: only use when the same panel pattern repeats. Otherwise inline directly.
"use client";

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

type PanelVariant = "surface" | "surfaceHi" | "paperWarm";

export interface PanelProps {
  t: ZenInkTokens;
  variant?: PanelVariant;
  outlined?: boolean;
  padding?: number | string;
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}

export function Panel({
  t,
  variant = "surface",
  outlined = true,
  padding = 16,
  children,
  style,
  className,
}: PanelProps) {
  const { c, radius } = t;

  const bgMap: Record<PanelVariant, string> = {
    surface: c.surface,
    surfaceHi: c.surfaceHi,
    paperWarm: c.paperWarm,
  };

  return (
    <div
      className={className}
      style={{
        background: bgMap[variant],
        border: outlined ? `1px solid ${c.inkHair}` : "none",
        borderRadius: radius,
        padding,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
