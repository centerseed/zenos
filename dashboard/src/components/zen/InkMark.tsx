// ZenOS · Zen Ink — Brand mark (enso with seal)
// Ported 1:1 from design-ref/components.jsx

import React from "react";

interface InkMarkProps {
  size?: number;
  ink: string;
  seal: string;
  sealInk: string;
  style?: React.CSSProperties;
}

export function InkMark({ size = 32, ink, seal, sealInk, style }: InkMarkProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 44 44" style={style}>
      <defs>
        <filter id="inkRough" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence baseFrequency="0.9" numOctaves="2" seed="3" />
          <feDisplacementMap in="SourceGraphic" scale="0.6" />
        </filter>
      </defs>
      <path
        d="M 22 6 A 16 16 0 1 1 10 35"
        fill="none"
        stroke={ink}
        strokeWidth="2.6"
        strokeLinecap="round"
        filter="url(#inkRough)"
        opacity="0.92"
      />
      <rect x="29" y="27" width="9" height="9" rx="1" fill={seal} opacity="0.9" />
      <text
        x="33.5"
        y="34"
        textAnchor="middle"
        fill={sealInk}
        fontSize="6.5"
        fontFamily="serif"
        fontWeight="700"
      >
        禪
      </text>
    </svg>
  );
}
