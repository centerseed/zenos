"use client";

// ZenOS · Zen Ink — HeroToday (shared between Home and Tasks)
// Ported 1:1 from design-ref/page_tasks.jsx lines 4-46

import { useInk } from "@/lib/zen-ink/tokens";
import { SealChop } from "./SealChop";
import { Chip } from "./Chip";

export function HeroToday() {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody, solarTerm } = t;

  return (
    <div
      style={{
        position: "relative",
        padding: "48px 48px 44px",
        borderBottom: `1px solid ${c.inkHair}`,
        background: c.paper,
        overflow: "hidden",
      }}
    >
      {/* Watermark 節氣 */}
      <div
        style={{
          position: "absolute",
          right: 36,
          top: 20,
          bottom: 20,
          display: "flex",
          alignItems: "center",
          pointerEvents: "none",
          fontFamily: fontHead,
          fontSize: 220,
          fontWeight: 500,
          color: c.ink,
          opacity: 0.04,
          letterSpacing: "0.1em",
          writingMode: "vertical-rl",
        }}
      >
        {solarTerm.name}
      </div>

      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "flex-start",
          gap: 28,
        }}
      >
        <SealChop text={solarTerm.name} seal={c.seal} sealInk={c.sealInk} size={60} />
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            2026 · 04 · 19 · SATURDAY
          </div>
          <h1
            style={{
              fontFamily: fontHead,
              fontSize: 44,
              fontWeight: 500,
              color: c.ink,
              margin: 0,
              letterSpacing: "0.04em",
              lineHeight: 1.1,
            }}
          >
            今日工作台
          </h1>
          <p
            style={{
              fontFamily: fontBody,
              fontSize: 14,
              color: c.inkMuted,
              margin: "12px 0 0",
              fontWeight: 400,
              letterSpacing: "0.02em",
            }}
          >
            今日有 3 項 P0 任務待處理，2 場會議，預計專注時段 3.5 小時。
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
            <Chip t={t} tone="accent" dot>
              2 · P0 待處理
            </Chip>
            <Chip t={t} tone="ocher" dot>
              3 · 進行中
            </Chip>
            <Chip t={t} tone="jade" dot>
              4 · 本週完成
            </Chip>
            <Chip t={t} tone="muted">
              專注時數 · 3.5h
            </Chip>
          </div>
        </div>
      </div>
    </div>
  );
}
