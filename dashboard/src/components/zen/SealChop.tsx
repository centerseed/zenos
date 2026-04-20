// ZenOS · Zen Ink — Seal chop (vertical 篆書 mark)
// Used as watermark / brand stamp
// Ported 1:1 from design-ref/components.jsx

import React from "react";

interface SealChopProps {
  text?: string;
  seal: string;
  sealInk: string;
  size?: number;
}

export function SealChop({ text = "禪作", seal, sealInk, size = 44 }: SealChopProps) {
  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        background: seal,
        color: sealInk,
        fontFamily: '"Noto Serif TC", "Songti TC", serif',
        fontWeight: 700,
        fontSize: size * 0.32,
        lineHeight: 1,
        letterSpacing: "0.05em",
        borderRadius: 2,
        boxShadow: `inset 0 0 0 1px rgba(255,242,236,0.12), inset 0 0 0 3px ${seal}`,
      }}
    >
      {text.split("").map((ch, i) => (
        <span key={i} style={{ padding: "1px 0" }}>
          {ch}
        </span>
      ))}
    </div>
  );
}
