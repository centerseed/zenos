// ZenOS · Landing — Variant A (濃禪 · sumi poetic)
// Sparse, vertical, literary; large seal; blank space as chapter breaks.
// Ported 1:1 from design-ref/landing_a.jsx
"use client";

import React from "react";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { LandingNav } from "../LandingNav";
import { LandingFooter } from "../LandingFooter";
import { FeatureCanvas } from "../FeatureCanvas";

interface LandingAProps {
  t: ZenInkTokens;
}

export function LandingA({ t }: LandingAProps) {
  const { c, fontHead, fontMono, fontBody } = t;

  return (
    <div style={{ background: c.paper, color: c.ink, fontFamily: fontBody }}>
      <LandingNav t={t} />

      {/* ── Hero ─────────────────────────────────────────── */}
      <section
        style={{
          position: "relative",
          minHeight: "92vh",
          padding: "120px 80px 80px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {/* Giant brush-stroke watermark */}
        <div
          style={{
            position: "absolute",
            right: -60,
            top: "18%",
            fontFamily: fontHead,
            fontSize: 380,
            lineHeight: 0.8,
            color: c.ink,
            opacity: 0.045,
            letterSpacing: "0.1em",
            writingMode: "vertical-rl",
            pointerEvents: "none",
            fontWeight: 500,
          }}
        >
          禪作
        </div>
        {/* Vertical seal line on right */}
        <div
          style={{
            position: "absolute",
            right: 80,
            top: 140,
            bottom: 60,
            width: 1,
            background: c.inkHair,
          }}
        />

        <div style={{ position: "relative", maxWidth: 820 }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 11,
              color: c.inkFaint,
              letterSpacing: "0.32em",
              textTransform: "uppercase",
              marginBottom: 40,
            }}
          >
            ZENOS · 2026 · Private Beta
          </div>
          <h1
            style={{
              fontFamily: fontHead,
              fontSize: 92,
              fontWeight: 500,
              color: c.ink,
              margin: 0,
              lineHeight: 1.08,
              letterSpacing: "0.06em",
            }}
          >
            一念起
            <br />
            萬事<span style={{ color: c.vermillion }}>有序</span>
          </h1>
          <div
            style={{
              width: 60,
              height: 1,
              background: c.ink,
              margin: "44px 0 36px",
            }}
          />
          <p
            style={{
              fontFamily: fontHead,
              fontSize: 19,
              color: c.inkMuted,
              lineHeight: 1.9,
              maxWidth: 560,
              margin: 0,
              letterSpacing: "0.08em",
              fontWeight: 400,
            }}
          >
            ZenOS 是為獨行者與團隊而造的知識工作台。
            <br />
            把散亂的思考、訊息、決定，收束成一道清明秩序。
          </p>
          <div
            style={{
              display: "flex",
              gap: 16,
              marginTop: 56,
              alignItems: "center",
            }}
          >
            <button
              style={{
                padding: "16px 32px",
                background: c.ink,
                color: c.paper,
                border: "none",
                borderRadius: 2,
                cursor: "pointer",
                fontFamily: fontBody,
                fontSize: 13,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
              }}
            >
              加入 Waitlist
            </button>
            <a
              style={{
                fontFamily: fontBody,
                fontSize: 12,
                color: c.inkMuted,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                cursor: "pointer",
                borderBottom: `1px solid ${c.inkHair}`,
                paddingBottom: 4,
              }}
            >
              觀看三分鐘演示 →
            </a>
          </div>
        </div>

        {/* bottom tagline */}
        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: 80,
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.24em",
            textTransform: "uppercase",
          }}
        >
          靜 · 觀 · 作 · 成
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 40,
            right: 80,
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.24em",
            textTransform: "uppercase",
          }}
        >
          ↓ 閱讀章節
        </div>
      </section>

      {/* ── 使用流程（三步章節）─────────────────────────── */}
      <section
        style={{
          padding: "140px 80px 120px",
          borderTop: `1px solid ${c.inkHair}`,
          background: c.paperWarm,
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.32em",
              textTransform: "uppercase",
              marginBottom: 20,
            }}
          >
            一 · ZENOS 之道
          </div>
          <h2
            style={{
              fontFamily: fontHead,
              fontSize: 52,
              fontWeight: 500,
              color: c.ink,
              margin: "0 0 80px",
              letterSpacing: "0.04em",
              lineHeight: 1.25,
              maxWidth: 720,
            }}
          >
            從繁瑣到澄明
            <br />
            只需三個呼吸
          </h2>

          <div
            style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0 }}
          >
            {[
              { num: "壹", en: "SETTLE",  zh: "安", title: "安頓你的世界", desc: "把所有散佈在訊息、文件、會議中的資料匯聚。Agent 會為你靜靜整理。" },
              { num: "貳", en: "OBSERVE", zh: "觀", title: "觀照當下要緊", desc: "每日早晨，ZenOS 呈給你一張清單，只留下真正需要你今天決定的事。" },
              { num: "參", en: "ACT",     zh: "作", title: "從容地行動",   desc: "任務、筆記、對話、客戶、文件，皆在同一方畫紙展開。專注在一件事。" },
            ].map((s, i) => (
              <div
                key={i}
                style={{
                  padding: "0 40px",
                  borderLeft: i > 0 ? `1px solid ${c.inkHair}` : "none",
                }}
              >
                <div
                  style={{
                    fontFamily: fontHead,
                    fontSize: 72,
                    fontWeight: 500,
                    color: c.vermillion,
                    letterSpacing: "0.06em",
                    lineHeight: 1,
                    marginBottom: 20,
                  }}
                >
                  {s.num}
                </div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.28em",
                    marginBottom: 12,
                  }}
                >
                  {s.en} · {s.zh}
                </div>
                <h3
                  style={{
                    fontFamily: fontHead,
                    fontSize: 26,
                    fontWeight: 500,
                    color: c.ink,
                    margin: "0 0 18px",
                    letterSpacing: "0.04em",
                    lineHeight: 1.35,
                  }}
                >
                  {s.title}
                </h3>
                <p
                  style={{
                    fontSize: 14,
                    color: c.inkMuted,
                    lineHeight: 1.9,
                    letterSpacing: "0.04em",
                    margin: 0,
                    fontFamily: fontHead,
                    fontWeight: 400,
                  }}
                >
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 功能亮點 · 一屏一特性 ───────────────────── */}
      {[
        {
          idx: "二",
          en: "KNOWLEDGE",
          zh: "知識地圖",
          en2: "Knowledge Graph",
          title: "一切關聯，皆在紙上。",
          body: "客戶、專案、文件、對話，不再各自為政。ZenOS 的知識地圖替你連起脈絡，任何一點都能回溯來處。",
          accent: "vermillion",
          // f.en.toLowerCase() = "knowledge"
          kind: "knowledge",
        },
        {
          idx: "三",
          en: "AGENT",
          zh: "靜默 Agent",
          en2: "Quiet Agent",
          title: "AI 不喧嘩，只做事。",
          body: "Agent 於背景運作：歸檔會議紀要、提醒未覆郵件、為客戶複盤草擬下一步。你只需在恰當的時機，翻閱它留下的筆記。",
          accent: "ink",
          // f.en.toLowerCase() = "agent"
          kind: "agent",
        },
        {
          idx: "四",
          en: "RHYTHM",
          zh: "節律",
          en2: "Rhythm",
          title: "日有日的工，月有月的成。",
          body: "以節氣與週期為脈，ZenOS 幫你維繫工作的呼吸：專注、休整、盤點、再出發。紀律不是約束，是自由的基石。",
          accent: "jade",
          // f.en.toLowerCase() = "rhythm"
          kind: "rhythm",
        },
      ].map((f, i) => (
        <section
          key={i}
          style={{
            padding: "140px 80px",
            borderTop: `1px solid ${c.inkHair}`,
            background: i % 2 ? c.paper : c.paperWarm,
          }}
        >
          <div
            style={{
              maxWidth: 1200,
              margin: "0 auto",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 80,
              alignItems: "center",
            }}
          >
            <div>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.32em",
                  textTransform: "uppercase",
                  marginBottom: 18,
                }}
              >
                {f.idx} · {f.en}
              </div>
              <div
                style={{
                  fontFamily: fontHead,
                  fontSize: 13,
                  color: c.vermillion,
                  letterSpacing: "0.24em",
                  marginBottom: 22,
                }}
              >
                {f.zh} / {f.en2}
              </div>
              <h3
                style={{
                  fontFamily: fontHead,
                  fontSize: 44,
                  fontWeight: 500,
                  color: c.ink,
                  margin: "0 0 30px",
                  letterSpacing: "0.04em",
                  lineHeight: 1.3,
                }}
              >
                {f.title}
              </h3>
              <p
                style={{
                  fontFamily: fontHead,
                  fontSize: 16,
                  color: c.inkMuted,
                  lineHeight: 2,
                  letterSpacing: "0.05em",
                  margin: 0,
                  fontWeight: 400,
                }}
              >
                {f.body}
              </p>
            </div>
            <FeatureCanvas t={t} variant={f.accent} kind={f.kind} />
          </div>
        </section>
      ))}

      {/* ── Manifesto ─────────────────────────────────── */}
      <section
        style={{
          padding: "180px 80px",
          borderTop: `1px solid ${c.inkHair}`,
          background: c.ink,
          color: c.paper,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            right: -40,
            top: 40,
            fontFamily: fontHead,
            fontSize: 340,
            lineHeight: 0.8,
            color: c.paper,
            opacity: 0.03,
            letterSpacing: "0.15em",
            pointerEvents: "none",
            writingMode: "vertical-rl",
          }}
        >
          心
        </div>
        <div style={{ maxWidth: 860, margin: "0 auto", position: "relative" }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: "rgba(244,239,228,0.5)",
              letterSpacing: "0.32em",
              textTransform: "uppercase",
              marginBottom: 30,
            }}
          >
            五 · MANIFESTO
          </div>
          <h2
            style={{
              fontFamily: fontHead,
              fontSize: 38,
              fontWeight: 400,
              color: c.paper,
              margin: 0,
              letterSpacing: "0.06em",
              lineHeight: 1.8,
            }}
          >
            工具本該退到背景，讓思考走到前臺。
            <br />
            我們相信，真正的效率不是更快地做更多，
            <br />
            而是清楚地知道何者必作、何者可捨。
            <br />
            <br />
            <span style={{ color: c.vermillion }}>願你以禪心，做實事。</span>
          </h2>
          <div
            style={{
              marginTop: 60,
              fontFamily: fontMono,
              fontSize: 11,
              color: "rgba(244,239,228,0.5)",
              letterSpacing: "0.24em",
            }}
          >
            — ZenOS 團隊 · 台北
          </div>
        </div>
      </section>

      {/* ── Final CTA ───────────────────────────── */}
      <section
        style={{
          padding: "140px 80px",
          textAlign: "center",
          borderTop: `1px solid ${c.inkHair}`,
          background: c.paper,
        }}
      >
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.32em",
            textTransform: "uppercase",
            marginBottom: 30,
          }}
        >
          六 · 入門
        </div>
        <h2
          style={{
            fontFamily: fontHead,
            fontSize: 64,
            fontWeight: 500,
            color: c.ink,
            margin: "0 0 40px",
            letterSpacing: "0.06em",
            lineHeight: 1.2,
          }}
        >
          此刻，便是起點。
        </h2>
        <p
          style={{
            fontFamily: fontHead,
            fontSize: 16,
            color: c.inkMuted,
            lineHeight: 1.9,
            maxWidth: 540,
            margin: "0 auto 56px",
            letterSpacing: "0.04em",
          }}
        >
          ZenOS 正在有限內測。
          <br />
          留下一封信，我們會親自邀請你進來。
        </p>
        <div
          style={{
            display: "flex",
            gap: 0,
            maxWidth: 480,
            margin: "0 auto",
            border: `1px solid ${c.inkHairBold}`,
            borderRadius: 2,
            background: c.surface,
          }}
        >
          <input
            placeholder="你的 email"
            style={{
              flex: 1,
              padding: "16px 20px",
              background: "transparent",
              border: "none",
              outline: "none",
              fontFamily: fontBody,
              fontSize: 14,
              color: c.ink,
            }}
          />
          <button
            style={{
              padding: "0 32px",
              background: c.ink,
              color: c.paper,
              border: "none",
              cursor: "pointer",
              fontFamily: fontBody,
              fontSize: 12,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
            }}
          >
            加入
          </button>
        </div>
        <div
          style={{
            marginTop: 32,
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.18em",
          }}
        >
          不發廣告 · 每月至多一封信
        </div>
      </section>

      <LandingFooter t={t} />
    </div>
  );
}
