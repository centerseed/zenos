// ZenOS · Zen Ink — Landing navigation bar
// Ported 1:1 from design-ref/landing_parts.jsx

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

interface LandingNavProps {
  t: ZenInkTokens;
}

export function LandingNav({ t }: LandingNavProps) {
  const { c, fontMono, fontHead } = t;
  return (
    <nav
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        padding: "18px 40px",
        display: "flex",
        alignItems: "center",
        gap: 40,
        background: `${c.paper}ee`,
        backdropFilter: "blur(12px)",
        borderBottom: `1px solid ${c.inkHair}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 26,
            height: 26,
            background: c.vermillion,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: fontHead,
            color: c.paper,
            fontSize: 15,
            letterSpacing: 0,
            borderRadius: 1,
          }}
        >
          禪
        </div>
        <div
          style={{
            fontFamily: fontHead,
            fontSize: 16,
            color: c.ink,
            letterSpacing: "0.18em",
            fontWeight: 500,
          }}
        >
          ZenOS
        </div>
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 9,
            color: c.inkFaint,
            letterSpacing: "0.24em",
            textTransform: "uppercase",
            padding: "3px 8px",
            border: `1px solid ${c.inkHair}`,
            marginLeft: 4,
          }}
        >
          Beta
        </div>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", gap: 28 }}>
        {["功能", "流程", "信念", "定價", "日誌"].map((x, i) => (
          <a
            key={i}
            style={{
              fontFamily: fontHead,
              fontSize: 13,
              color: c.inkSoft,
              letterSpacing: "0.16em",
              cursor: "pointer",
            }}
          >
            {x}
          </a>
        ))}
      </div>
      <button
        style={{
          padding: "9px 22px",
          background: c.ink,
          color: c.paper,
          border: "none",
          borderRadius: 2,
          cursor: "pointer",
          fontFamily: "inherit",
          fontSize: 12,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
        }}
      >
        加入 Waitlist
      </button>
    </nav>
  );
}
