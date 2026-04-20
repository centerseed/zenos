// ZenOS · Zen Ink — Chip (status badge)
// Ported 1:1 from design-ref/components.jsx
"use client";

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

type ChipTone = "muted" | "accent" | "jade" | "ocher" | "plain";

interface ChipProps {
  children: React.ReactNode;
  t: ZenInkTokens;
  tone?: ChipTone;
  dot?: boolean;
  style?: React.CSSProperties;
}

export function Chip({ children, t, tone = "muted", dot, style }: ChipProps) {
  const { c, fontBody } = t;
  const tones: Record<ChipTone, { fg: string; bd: string }> = {
    muted: { fg: c.inkMuted, bd: c.inkHair },
    accent: { fg: c.vermillion, bd: c.vermLine },
    jade: { fg: c.jade, bd: c.inkHair },
    ocher: { fg: c.ocher, bd: c.inkHair },
    plain: { fg: c.inkMuted, bd: "transparent" },
  };
  const tn = tones[tone] ?? tones.muted;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "2px 8px",
        color: tn.fg,
        border: `1px solid ${tn.bd}`,
        borderRadius: 2,
        fontSize: 11,
        lineHeight: "16px",
        fontFamily: fontBody,
        fontWeight: 400,
        letterSpacing: "0.02em",
        ...style,
      }}
    >
      {dot && (
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: tn.fg,
          }}
        />
      )}
      {children}
    </span>
  );
}
