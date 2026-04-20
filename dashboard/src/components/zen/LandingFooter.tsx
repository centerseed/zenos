// ZenOS · Zen Ink — Landing footer
// Ported 1:1 from design-ref/landing_parts.jsx

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";

interface LandingFooterProps {
  t: ZenInkTokens;
}

export function LandingFooter({ t }: LandingFooterProps) {
  const { c, fontMono, fontHead } = t;
  return (
    <footer
      style={{
        padding: "80px 80px 40px",
        borderTop: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
        color: c.inkMuted,
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr",
          gap: 60,
        }}
      >
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 20,
            }}
          >
            <div
              style={{
                width: 22,
                height: 22,
                background: c.vermillion,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: fontHead,
                color: c.paper,
                fontSize: 13,
              }}
            >
              禪
            </div>
            <div
              style={{
                fontFamily: fontHead,
                fontSize: 14,
                color: c.ink,
                letterSpacing: "0.18em",
              }}
            >
              ZenOS
            </div>
          </div>
          <p
            style={{
              fontSize: 12,
              lineHeight: 1.9,
              maxWidth: 320,
              margin: 0,
              fontFamily: fontHead,
              letterSpacing: "0.04em",
            }}
          >
            為獨行者與小隊而造的知識工作台。
            <br />
            一方畫紙，收束散亂思緒。
          </p>
        </div>
        {[
          { h: "產品", items: ["功能地圖", "路線圖", "更新日誌", "定價"] },
          { h: "團隊", items: ["關於我們", "信念書", "職缺", "媒體包"] },
          { h: "聯繫", items: ["support@zenos.tw", "Twitter / X", "台北 · 信義"] },
        ].map((col, i) => (
          <div key={i}>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.28em",
                textTransform: "uppercase",
                marginBottom: 18,
              }}
            >
              {col.h}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {col.items.map((x, j) => (
                <a
                  key={j}
                  style={{
                    fontFamily: fontHead,
                    fontSize: 13,
                    color: c.inkSoft,
                    cursor: "pointer",
                    letterSpacing: "0.04em",
                  }}
                >
                  {x}
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div
        style={{
          maxWidth: 1200,
          margin: "60px auto 0",
          paddingTop: 24,
          borderTop: `1px solid ${c.inkHair}`,
          display: "flex",
          justifyContent: "space-between",
          fontFamily: fontMono,
          fontSize: 10,
          color: c.inkFaint,
          letterSpacing: "0.18em",
        }}
      >
        <span>© 2026 ZENOS · 台北 · 穀雨版</span>
        <span>靜 · 觀 · 作 · 成</span>
      </div>
    </footer>
  );
}
