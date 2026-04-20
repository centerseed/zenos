// ZenOS · Zen Ink — Section title with east-style vertical mark
// Ported 1:1 from design-ref/components.jsx

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

interface SectionProps {
  num?: string;
  eyebrow?: string;
  title: string;
  en?: string;
  subtitle?: string;
  right?: React.ReactNode;
  t: ZenInkTokens;
}

export function Section({ num, eyebrow, title, en, subtitle, right, t }: SectionProps) {
  const { c, fontHead, fontMono } = t;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: 24,
        marginBottom: 28,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
        {num && (
          <div
            style={{
              writingMode: "vertical-rl",
              textOrientation: "mixed",
              fontFamily: fontHead,
              fontSize: 11,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              paddingTop: 4,
              borderRight: `1px solid ${c.inkHair}`,
              paddingRight: 10,
              marginRight: 4,
            }}
          >
            {num}
          </div>
        )}
        <div>
          {eyebrow && (
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              {eyebrow}
            </div>
          )}
          <h2
            style={{
              fontFamily: fontHead,
              fontSize: 34,
              fontWeight: 500,
              color: c.ink,
              margin: 0,
              letterSpacing: "0.02em",
              lineHeight: 1.1,
            }}
          >
            {title}
            {en && (
              <span
                style={{
                  marginLeft: 14,
                  fontFamily: '"Helvetica Neue", Helvetica, serif',
                  fontWeight: 300,
                  fontSize: 22,
                  color: c.inkFaint,
                  letterSpacing: "-0.01em",
                  fontStyle: "italic",
                }}
              >
                {en}
              </span>
            )}
          </h2>
          {subtitle && (
            <p
              style={{
                fontSize: 13,
                color: c.inkMuted,
                margin: "10px 0 0",
                maxWidth: 620,
                lineHeight: 1.65,
                fontWeight: 300,
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {right && <div style={{ paddingBottom: 6 }}>{right}</div>}
    </div>
  );
}
