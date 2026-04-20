// ZenOS · Zen Ink — Command Palette modal (⌘K)
// Ported 1:1 from design-ref/components.jsx
"use client";

import React, { useState, useEffect, useRef } from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "./Icons";

interface CmdKProps {
  t: ZenInkTokens;
  open: boolean;
  onClose: () => void;
}

export function CmdK({ t, open, onClose }: CmdKProps) {
  const { c, fontHead, fontBody, fontMono } = t;
  const [q, setQ] = useState("");
  const inpRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => inpRef.current?.focus(), 20);
    }
  }, [open]);

  if (!open) return null;

  const groups = [
    {
      g: "Agent Actions",
      items: [
        { l: "產生本週回顧摘要", h: "Summary" },
        { l: "列出所有阻塞的 P0 任務", h: "Triage" },
        { l: "草擬給 Acme 的後續信件", h: "CRM" },
      ],
    },
    {
      g: "跳轉",
      items: [
        { l: "知識地圖", h: "G M" },
        { l: "任務看板", h: "G T" },
        { l: "客戶", h: "G C" },
      ],
    },
  ];

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(20,18,16,0.42)",
        backdropFilter: "blur(10px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "13vh",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 640,
          maxWidth: "92%",
          background: c.surfaceHi,
          border: `1px solid ${c.inkHairBold}`,
          borderRadius: 2,
          overflow: "hidden",
          boxShadow: "0 40px 80px rgba(20,18,16,0.25)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "16px 20px",
            borderBottom: `1px solid ${c.inkHair}`,
          }}
        >
          <Icon d={ICONS.search} size={16} style={{ color: c.inkMuted }} />
          <input
            ref={inpRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜尋或輸入指令…"
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: c.ink,
              fontSize: 16,
              fontFamily: fontHead,
              fontWeight: 400,
              letterSpacing: "0.02em",
            }}
          />
          <kbd style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>
            ESC
          </kbd>
        </div>
        <div style={{ maxHeight: 440, overflow: "auto" }}>
          {groups.map((g, gi) => (
            <div key={gi}>
              <div
                style={{
                  padding: "12px 20px 6px",
                  fontFamily: fontMono,
                  fontSize: 9,
                  color: c.inkFaint,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                }}
              >
                {g.g}
              </div>
              {g.items.map((it, ii) => (
                <button
                  key={ii}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    width: "100%",
                    padding: "10px 20px",
                    background: "transparent",
                    border: "none",
                    color: c.ink,
                    cursor: "pointer",
                    fontSize: 13,
                    textAlign: "left",
                    fontFamily: fontBody,
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = c.surface)
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  <Icon
                    d={ICONS.spark}
                    size={13}
                    style={{ color: c.vermillion }}
                  />
                  <span style={{ flex: 1 }}>{it.l}</span>
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: c.inkFaint,
                    }}
                  >
                    {it.h}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
