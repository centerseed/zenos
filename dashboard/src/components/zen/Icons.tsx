// ZenOS · Zen Ink — Icon glyphs (calligraphic weight)
// Ported 1:1 from design-ref/components.jsx
// Note: namespace renamed from Icons → ICONS to avoid conflict with Icon component.

import React from "react";

interface IconProps {
  d: string | React.ReactNode;
  size?: number;
  stroke?: number;
  style?: React.CSSProperties;
}

export function Icon({ d, size = 16, stroke = 1.4, style = {} }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}
    >
      {typeof d === "string" ? <path d={d} /> : d}
    </svg>
  );
}

export const ICONS = {
  search:
    "M11 19a8 8 0 100-16 8 8 0 000 16zm10 2l-4.35-4.35",
  plus: "M12 5v14M5 12h14",
  chev: "M9 6l6 6-6 6",
  zen: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12a9 9 0 0118 0" />
    </>
  ),
  task: "M4 6h16M4 12h16M4 18h10",
  folder:
    "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z",
  users:
    "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8z",
  map: "M9 3L2 6v15l7-3 6 3 7-3V3l-7 3-6-3zM9 3v15M15 6v15",
  trend:
    "M3 17l6-6 4 4 8-8M14 7h7v7",
  doc: "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6",
  spark:
    "M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  filter: "M3 6h18M6 12h12M10 18h4",
  settings:
    "M12 15a3 3 0 100-6 3 3 0 000 6zm7.4-3a7.4 7.4 0 00-.1-1.4l2-1.6-2-3.4-2.4.8a7.4 7.4 0 00-2.4-1.4L14 2h-4l-.5 2.6a7.4 7.4 0 00-2.4 1.4l-2.4-.8-2 3.4 2 1.6a7.4 7.4 0 000 2.8l-2 1.6 2 3.4 2.4-.8a7.4 7.4 0 002.4 1.4L10 22h4l.5-2.6a7.4 7.4 0 002.4-1.4l2.4.8 2-3.4-2-1.6z",
  moon: "M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z",
  sun: "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 7a5 5 0 110 10 5 5 0 010-10z",
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  link: "M10 14a5 5 0 017 0l3-3a5 5 0 10-7-7l-1 1m-2 8a5 5 0 01-7 0l-3 3a5 5 0 107 7l1-1",
  check: "M5 13l4 4L19 7",
};
