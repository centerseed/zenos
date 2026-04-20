// ZenOS · Zen Ink — Hairline divider (subtle brush texture via gradient)
// Ported 1:1 from design-ref/components.jsx

import React from "react";

interface DividerProps {
  ink: string;
  style?: React.CSSProperties;
  vertical?: boolean;
}

export function Divider({ ink, style, vertical }: DividerProps) {
  return (
    <div
      style={{
        [vertical ? "width" : "height"]: 1,
        [vertical ? "height" : "width"]: "100%",
        background: `linear-gradient(${vertical ? "180deg" : "90deg"}, transparent 0%, ${ink} 15%, ${ink} 85%, transparent 100%)`,
        opacity: 0.6,
        ...style,
      }}
    />
  );
}
