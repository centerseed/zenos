"use client";

// Named re-exports kept for test files that import from this path.
export {
  CampaignDetail,
  CampaignList,
  CampaignStarter,
  CoworkChatSheet,
  FlowGuideSheet,
  PromptManagerSheet,
  StrategyAndPlan,
  StrategyPlanner,
  StyleManager,
  TopicStarter,
} from "@/features/marketing/MarketingWorkspace";

// Default export: Zen Ink real-data wired marketing page (S04)
export { default } from "@/features/marketing/ZenInkMarketingWorkspace";

import React, { Fragment, useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Btn } from "@/components/zen/Btn";
import { Chip } from "@/components/zen/Chip";
import { Section } from "@/components/zen/Section";

// ─── Demo data ────────────────────────────────────────────────────────────────

const MKT_CAMPAIGNS = [
  { id: "c1", title: "Naruvia 官網部落格",        desc: "Naruvia 官網的部落格運營與 SEO 策略，透過內容行銷提升品牌聲量與轉換。", channel: "Blog · EDM", status: "drafting",  owner: "子豪", due: "04/22", perf: 0.62, stage: 2 },
  { id: "c2", title: "Q2 產品發表：ZenOS 2.0",   desc: "ZenOS 2.0 的整季發表策略與素材管理。",                                    channel: "Launch",     status: "approved",  owner: "品瑄", due: "05/01", perf: 0.88, stage: 5 },
  { id: "c3", title: "客戶案例：Acme 協作流程",  desc: "拆解 Acme 與 ZenOS 的協作過程，作為 Case Study。",                       channel: "Case Study", status: "in_review", owner: "Me",   due: "04/25", perf: 0.41, stage: 4 },
  { id: "c4", title: "開發者文件更新 v2",         desc: "Docs v2 的寫作與發佈計畫。",                                              channel: "Docs",       status: "drafting",  owner: "怡君", due: "05/03", perf: 0.35, stage: 1 },
];

type MktStatus = "drafting" | "in_review" | "approved";

const MKT_STATUS: Record<MktStatus, { tone: "muted" | "ocher" | "jade"; label: string }> = {
  drafting:  { tone: "muted", label: "撰寫中" },
  in_review: { tone: "ocher", label: "審查中" },
  approved:  { tone: "jade",  label: "已核准" },
};

const MKT_STAGES = ["策略", "排程", "情報", "生成", "確認", "發佈"];

type Campaign = typeof MKT_CAMPAIGNS[number];

// ─── Back-arrow path ─────────────────────────────────────────────────────────

const ARROW_LEFT = "M19 12H5M12 19l-7-7 7-7";

// ─── Campaign list ────────────────────────────────────────────────────────────

function InkMktList({ onOpen }: { onOpen: (id: string) => void }) {
  const t = useInk();
  const { c, fontHead, fontMono, fontBody } = t;

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section
        t={t}
        eyebrow="GROWTH · 行銷"
        title="行銷"
        en="Marketing"
        subtitle="與 Agent 共筆文案、品牌聲音與素材；一個地方管理所有渠道。"
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <Btn t={t} variant="ghost" icon={ICONS.doc}>品牌手冊</Btn>
            <Btn t={t} variant="outline" icon={ICONS.spark}>Agent 寫一則</Btn>
            <Btn t={t} variant="seal" icon={ICONS.plus}>新 Campaign</Btn>
          </div>
        }
      />

      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}`, marginBottom: 24 }}>
        {[
          { k: "進行中",     v: "4",     sub: "2 個本週到期" },
          { k: "本月觸及",   v: "24.3k", sub: "↑ 18% MoM" },
          { k: "轉換率",     v: "3.2%",  sub: "Benchmark 2.4%" },
          { k: "Agent 草稿", v: "7",     sub: "3 份待審" },
        ].map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>{s.k}</div>
            <div style={{ fontFamily: fontHead, fontSize: 28, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Campaign table */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.inkHair}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontFamily: fontHead, fontSize: 14, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>Campaigns</span>
          <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em" }}>{MKT_CAMPAIGNS.length} ITEMS</span>
        </div>
        {MKT_CAMPAIGNS.map((k, i) => {
          const st = MKT_STATUS[k.status as MktStatus];
          return (
            <button
              key={k.id}
              onClick={() => onOpen(k.id)}
              style={{
                display: "grid", gridTemplateColumns: "24px 1fr 140px 90px 90px",
                alignItems: "center", gap: 12, padding: "14px 16px", width: "100%",
                background: "transparent", border: "none",
                borderLeft: "2px solid transparent", borderBottom: `1px solid ${c.inkHair}`,
                color: c.ink, cursor: "pointer", textAlign: "left", fontFamily: fontBody,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = c.surfaceHi; e.currentTarget.style.borderLeftColor = c.vermillion; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderLeftColor = "transparent"; }}
            >
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>{String(i + 1).padStart(2, "0")}</span>
              <div>
                <div style={{ fontSize: 14, color: c.ink, fontWeight: 500, letterSpacing: "0.02em" }}>{k.title}</div>
                <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 3, display: "flex", gap: 8 }}>
                  <span>{k.channel}</span>
                  <span style={{ color: c.inkFaint }}>·</span>
                  <span>{k.owner}</span>
                  <span style={{ color: c.inkFaint }}>·</span>
                  <span style={{ fontFamily: fontMono }}>{k.due}</span>
                </div>
              </div>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkMuted, letterSpacing: "0.08em" }}>
                階段 · {MKT_STAGES[k.stage]}
              </span>
              <div>
                <div style={{ height: 3, background: c.inkHair, position: "relative", overflow: "hidden" }}>
                  <div style={{ position: "absolute", inset: 0, width: `${k.perf * 100}%`, background: k.perf > 0.7 ? c.jade : k.perf > 0.5 ? c.vermillion : c.ocher }} />
                </div>
                <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, marginTop: 3, textAlign: "right" }}>{Math.round(k.perf * 100)}%</div>
              </div>
              <Chip t={t} tone={st.tone} dot style={{ justifySelf: "start" }}>{st.label}</Chip>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Campaign detail ──────────────────────────────────────────────────────────

function InkMktDetail({ campaign, onBack }: { campaign: Campaign; onBack: () => void }) {
  const t = useInk();
  const { c, fontHead, fontMono, fontBody } = t;
  const [stage, setStage] = useState<number>(campaign.stage);
  const st = MKT_STATUS[campaign.status as MktStatus];

  return (
    <div style={{ padding: "32px 48px 60px", maxWidth: 1600 }}>
      {/* Back */}
      <button
        onClick={onBack}
        style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          background: "transparent", border: "none", color: c.inkMuted,
          cursor: "pointer", fontFamily: fontBody, fontSize: 12,
          padding: "4px 8px 4px 0", marginBottom: 18, letterSpacing: "0.02em",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = c.ink)}
        onMouseLeave={(e) => (e.currentTarget.style.color = c.inkMuted)}
      >
        <Icon d={ARROW_LEFT} size={14} />
        返回 Campaigns
      </button>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, marginBottom: 28 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
              CAMPAIGN · {campaign.channel}
            </span>
            <Chip t={t} tone={st.tone} dot>{st.label}</Chip>
          </div>
          <h1 style={{ fontFamily: fontHead, fontSize: 34, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.02em", lineHeight: 1.15 }}>
            {campaign.title}
          </h1>
          <p style={{ fontSize: 13, color: c.inkMuted, margin: "10px 0 0", maxWidth: 700, lineHeight: 1.7 }}>
            {campaign.desc}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, paddingTop: 4 }}>
          <Btn t={t} variant="ghost" size="sm" icon={ICONS.doc}>Brief</Btn>
          <Btn t={t} variant="outline" size="sm" icon={ICONS.link}>分享</Btn>
          <Btn t={t} variant="ink" size="sm" icon={ICONS.check}>標記完成</Btn>
        </div>
      </div>

      {/* Stepper */}
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        padding: "14px 18px", background: c.surface,
        border: `1px solid ${c.inkHair}`, borderRadius: 2, marginBottom: 24,
      }}>
        {MKT_STAGES.map((s, i) => {
          const done = i < stage;
          const cur = i === stage;
          return (
            <Fragment key={i}>
              <button
                onClick={() => setStage(i)}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 7,
                  padding: "6px 12px",
                  background: cur ? c.vermSoft : "transparent",
                  border: `1px solid ${cur ? c.vermLine : done ? c.inkHair : "transparent"}`,
                  borderRadius: 2, cursor: "pointer",
                  fontFamily: fontBody, fontSize: 12,
                  color: cur ? c.vermillion : done ? c.ink : c.inkFaint,
                  fontWeight: cur ? 500 : 400, letterSpacing: "0.04em",
                  transition: "all .15s",
                }}
              >
                <span style={{
                  width: 16, height: 16, borderRadius: "50%",
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  background: cur ? c.vermillion : done ? c.ink : "transparent",
                  border: `1px solid ${cur ? c.vermillion : done ? c.ink : c.inkHair}`,
                  color: cur || done ? c.paper : c.inkFaint,
                  fontFamily: fontMono, fontSize: 9, fontWeight: 600,
                }}>
                  {done ? "✓" : i + 1}
                </span>
                {s}
              </button>
              {i < MKT_STAGES.length - 1 && (
                <div style={{ width: 16, height: 1, background: i < stage ? c.ink : c.inkHair }} />
              )}
            </Fragment>
          );
        })}
      </div>

      {/* Content grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Current stage card */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
              <div>
                <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 6 }}>
                  目前階段 · {MKT_STAGES[stage]}
                </div>
                <div style={{ fontFamily: fontHead, fontSize: 18, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                  先補情報
                </div>
                <div style={{ fontSize: 12.5, color: c.inkMuted, marginTop: 6, lineHeight: 1.6 }}>
                  主題已建立。先跑 <code style={{ fontFamily: fontMono, fontSize: 11, background: c.paperWarm, padding: "1px 5px", borderRadius: 2 }}>/marketing-intel</code> 蒐集近期訊號。
                </div>
              </div>
              <Chip t={t} tone="accent" dot>目前階段</Chip>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["按「帶進 AI」開始", "集中在同一個 AI 工作區討論", "有 structured result 才套用"].map((h, i) => (
                <Chip key={i} t={t} tone="muted">{h}</Chip>
              ))}
            </div>
          </div>

          {/* Strategy + writing plan */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <div style={{ fontFamily: fontHead, fontSize: 15, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                  建立行銷寫作計畫
                </div>
                <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 4 }}>
                  先和 AI 討論策略，不再由手填一堆欄位。
                </div>
              </div>
              <Btn t={t} variant="outline" size="sm" icon={ICONS.spark}>先帶進 AI</Btn>
            </div>
            <div style={{
              padding: "11px 14px", background: c.paper,
              border: `1px solid ${c.inkHair}`, borderRadius: 2,
              fontSize: 12.5, color: c.inkMuted, fontFamily: fontBody, marginBottom: 10,
            }}>
              AI 工作區會沿用同一套對話、權限、diff 與寫回流程。策略討論完可直接套用到下方欄位。
            </div>
            <details style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 12, marginTop: 12 }}>
              <summary style={{
                display: "flex", alignItems: "center", gap: 8,
                fontSize: 12, color: c.ink, cursor: "pointer",
                fontFamily: fontBody, letterSpacing: "0.02em",
                listStyle: "none",
              }}>
                <Icon d={ICONS.chev} size={12} style={{ color: c.inkFaint }} />
                手動微調策略（進階）
              </summary>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12 }}>
                <span style={{ fontSize: 12, color: c.inkMuted }}>欄位已育，可直接儲存。</span>
                <Btn t={t} variant="seal" size="sm">儲存策略</Btn>
              </div>
            </details>
          </div>

          {/* Style manager */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <div style={{ fontFamily: fontHead, fontSize: 15, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                  文風管理
                </div>
                <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 4 }}>
                  三層 style 可直接 CRUD；預覽測試會直接本機 helper 產生測試文案。
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <Chip t={t} tone="muted">長期項目</Chip>
                <Btn t={t} variant="outline" size="sm" icon={ICONS.spark}>帶進 AI</Btn>
              </div>
            </div>
            <div style={{
              padding: "11px 14px", background: c.paper,
              border: `1px solid ${c.inkHair}`, borderRadius: 2,
              fontSize: 12.5, color: c.inkMuted, marginBottom: 10,
            }}>
              尚未建立文風。可先新增 project 級 style。
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 180px auto", gap: 8 }}>
              <input
                placeholder="文風標題"
                style={{
                  padding: "8px 12px", background: c.paper,
                  border: `1px solid ${c.inkHair}`, borderRadius: 2,
                  fontFamily: fontBody, fontSize: 12, color: c.ink, outline: "none",
                }}
              />
              <select
                style={{
                  padding: "8px 12px", background: c.paper,
                  border: `1px solid ${c.inkHair}`, borderRadius: 2,
                  fontFamily: fontBody, fontSize: 12, color: c.ink, outline: "none",
                }}
              >
                <option>Project 級</option>
                <option>Team 級</option>
                <option>Global 級</option>
              </select>
              <Btn t={t} variant="ink" size="sm" icon={ICONS.plus}>新增</Btn>
            </div>
          </div>
        </div>

        {/* Right AI rail */}
        <div style={{
          background: c.paperWarm, border: `1px solid ${c.inkHair}`,
          borderRadius: 2, padding: 18,
          display: "flex", flexDirection: "column", gap: 14,
          position: "sticky", top: 20, alignSelf: "flex-start",
          maxHeight: "calc(100vh - 80px)",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontFamily: fontHead, fontSize: 14, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                Marketing AI Rail
              </div>
              <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>全域對話</div>
            </div>
            <Chip t={t} tone="muted">等待輸入</Chip>
          </div>
          <div>
            <div style={{ fontSize: 12.5, color: c.ink, fontWeight: 500, lineHeight: 1.5 }}>
              先從一區塊把內容帶進 AI
            </div>
            <div style={{ fontSize: 11.5, color: c.inkMuted, lineHeight: 1.7, marginTop: 6 }}>
              保留最必要的上下文操作。為了能診斷資訊將滿塞滿整個面板。
            </div>
          </div>
          <button style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "8px 12px", background: c.surfaceHi,
            border: `1px solid ${c.inkHair}`, borderRadius: 2,
            color: c.ink, fontFamily: fontBody, fontSize: 12, cursor: "pointer",
            letterSpacing: "0.02em",
          }}>
            <Icon d={ICONS.spark} size={12} style={{ color: c.vermillion }} />
            Connector 已連接
          </button>
          <div style={{
            padding: 14, background: c.surface,
            border: `1px solid ${c.inkHair}`, borderRadius: 2,
          }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 6 }}>
              AI 工作區
            </div>
            <div style={{ fontSize: 12, color: c.ink, lineHeight: 1.6 }}>
              先從任一區塊按「帶進 AI」，再開始討論。
            </div>
          </div>
          <details>
            <summary style={{
              listStyle: "none", display: "flex", alignItems: "center", gap: 6,
              cursor: "pointer", fontFamily: fontMono, fontSize: 10,
              color: c.inkMuted, letterSpacing: "0.14em", textTransform: "uppercase",
            }}>
              <Icon d={ICONS.chev} size={11} />
              查看 prompt / context
            </summary>
          </details>
          <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 12, marginTop: 4 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, letterSpacing: "0.04em" }}>
                對話
              </span>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>可聊天</span>
            </div>
            <div style={{
              padding: "8px 10px", background: c.surface,
              border: `1px solid ${c.inkHair}`, borderRadius: 2,
              fontSize: 12, color: c.inkFaint,
            }}>
              問 Agent，或 @ 成員…
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Page entry ───────────────────────────────────────────────────────────────

function InkMktPage() {
  const [openId, setOpenId] = useState<string | null>(null);
  const campaign = MKT_CAMPAIGNS.find(c => c.id === openId);

  if (openId && campaign) {
    return <InkMktDetail campaign={campaign} onBack={() => setOpenId(null)} />;
  }
  return <InkMktList onOpen={setOpenId} />;
}

// default export now re-exported from ZenInkMarketingWorkspace (see top of file)
