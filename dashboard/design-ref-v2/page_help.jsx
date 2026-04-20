// ZenOS v2 · Help & Support (幫助中心)
const { useState: useHelpS } = React;

const HELP_CATS = [
  { k: "start",     zh: "上手指南",      en: "Getting Started", icon: Icons.sparkle, count: 8 },
  { k: "map",       zh: "知識地圖",      en: "Knowledge Map",   icon: Icons.map,     count: 12 },
  { k: "agent",     zh: "Agent · 共筆",   en: "Agent & Cowork",  icon: Icons.agent,   count: 9 },
  { k: "tasks",     zh: "任務與節律",    en: "Tasks & Rhythm",  icon: Icons.tasks,   count: 7 },
  { k: "integrate", zh: "整合 · MCP",    en: "Integrations",    icon: Icons.link,    count: 14 },
  { k: "billing",   zh: "帳號與帳務",    en: "Account",         icon: Icons.wallet,  count: 6 },
];

const POPULAR = [
  { q: "如何建立我的第一張知識地圖？", cat: "知識地圖", read: "3 分鐘" },
  { q: "Agent 共筆的三種模式有什麼差別？", cat: "Agent", read: "4 分鐘" },
  { q: "為什麼我的 MCP 連線會失敗？", cat: "整合", read: "2 分鐘" },
  { q: "如何將 ZenOS 的任務同步到 Linear？", cat: "整合", read: "5 分鐘" },
  { q: "晨報的內容是如何生成的？", cat: "上手指南", read: "3 分鐘" },
];

const CONTACT_HISTORY = [
  { id: "t-0421", subj: "Notion 同步延遲",       status: "replied", at: "今日 11:20", by: "Claire · 客服" },
  { id: "t-0418", subj: "API 金鑰設定問題",       status: "closed",  at: "3 天前",     by: "Eric · 技術" },
  { id: "t-0402", subj: "付款發票抬頭修改",       status: "closed",  at: "2 週前",     by: "April · 帳務" },
];

function InkHelpPage({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [q, setQ] = useHelpS("");

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="HELP · 幫助" title="幫助中心" en="Help & Support"
        subtitle="文件、教學、聯繫支援。我們通常在 4 小時內回覆。"
      />

      {/* Hero search */}
      <div style={{
        padding: "36px 40px 32px", marginBottom: 28,
        background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2,
        position: "relative", overflow: "hidden",
      }}>
        {/* Seasonal watermark */}
        <div style={{
          position: "absolute", right: 36, top: 24, fontFamily: fontHead,
          fontSize: 120, color: c.inkHair, letterSpacing: "0.08em",
          lineHeight: 1, userSelect: "none", pointerEvents: "none",
        }}>問</div>

        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 10 }}>
          ASK · 請問
        </div>
        <div style={{ fontFamily: fontHead, fontSize: 30, fontWeight: 500, color: c.ink, letterSpacing: "0.05em", marginBottom: 6 }}>
          有什麼能幫上你？
        </div>
        <div style={{ fontSize: 13, color: c.inkMuted, marginBottom: 20, lineHeight: 1.7 }}>
          輸入一個問題，Agent 會為你尋找最相關的文件、教學與社群討論。
        </div>

        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "12px 18px", maxWidth: 640,
          background: c.surface, border: `1px solid ${c.inkHairBold}`, borderRadius: 2,
        }}>
          <Icon d={Icons.search} size={16} style={{ color: c.inkMuted }} />
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="例如：如何建立知識節點？" style={{
            flex: 1, background: "transparent", border: "none", outline: "none",
            color: c.ink, fontSize: 15, fontFamily: fontBody, letterSpacing: "0.02em",
          }} />
          <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em" }}>⌘K</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
          <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginRight: 4 }}>
            熱門 ·
          </span>
          {["晨報怎麼看", "邀請成員", "MCP 設定", "刪除節點", "快捷鍵"].map(s => (
            <button key={s} style={{
              padding: "3px 10px", background: c.surface,
              border: `1px solid ${c.inkHair}`, borderRadius: 2,
              color: c.inkSoft, fontSize: 11, fontFamily: fontBody, cursor: "pointer", letterSpacing: "0.02em",
            }}>{s}</button>
          ))}
        </div>
      </div>

      {/* Main grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 28 }}>
        {/* Left column */}
        <div>
          {/* Categories */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
              <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                瀏覽主題
              </div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
                Browse by topic
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}` }}>
              {HELP_CATS.map(cat => (
                <button key={cat.k} style={{
                  background: c.surface, border: "none", padding: "18px 18px 16px",
                  cursor: "pointer", textAlign: "left", fontFamily: fontBody,
                  display: "flex", flexDirection: "column", gap: 10,
                  transition: "all .15s",
                }}
                  onMouseEnter={e => e.currentTarget.style.background = c.paperWarm}
                  onMouseLeave={e => e.currentTarget.style.background = c.surface}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{
                      width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center",
                      background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2,
                      color: c.vermillion,
                    }}>
                      <Icon d={cat.icon} size={15} />
                    </div>
                    <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>
                      {cat.count} 篇
                    </span>
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: c.ink, letterSpacing: "0.03em" }}>{cat.zh}</div>
                    <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em", marginTop: 3, textTransform: "uppercase" }}>
                      {cat.en}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Popular articles */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
              <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                本週熱問
              </div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
                Popular this week
              </div>
              <div style={{ flex: 1 }} />
              <button style={{
                background: "transparent", border: "none", color: c.vermillion,
                fontFamily: fontBody, fontSize: 12, cursor: "pointer", letterSpacing: "0.04em",
              }}>查看全部 →</button>
            </div>
            <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
              {POPULAR.map((a, i) => (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "28px 1fr 100px 80px",
                  gap: 14, alignItems: "center",
                  padding: "14px 18px",
                  borderBottom: i < POPULAR.length - 1 ? `1px solid ${c.inkHair}` : "none",
                  cursor: "pointer", transition: "background .12s",
                }}
                  onMouseEnter={e => e.currentTarget.style.background = c.paperWarm}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <div style={{
                    fontFamily: fontMono, fontSize: 11, color: c.inkFaint,
                    letterSpacing: "0.1em", textAlign: "center",
                  }}>
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div style={{ fontSize: 13.5, color: c.ink, letterSpacing: "0.02em" }}>{a.q}</div>
                  <Chip t={t} tone="muted">{a.cat}</Chip>
                  <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkFaint, letterSpacing: "0.04em", textAlign: "right" }}>
                    {a.read}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Keyboard shortcuts */}
          <div style={{ background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 22 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 16 }}>
              <div style={{ fontFamily: fontHead, fontSize: 15, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                快捷鍵
              </div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
                Shortcuts
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 28px" }}>
              {[
                ["⌘K",        "指令面板 · Command"],
                ["⌘⇧N",       "新節點 · New node"],
                ["⌘J",        "召喚 Agent · Summon Agent"],
                ["G then H",  "回首頁 · Home"],
                ["G then M",  "知識地圖 · Map"],
                ["G then T",  "任務 · Tasks"],
                ["⌘B",        "切換側欄 · Toggle sidebar"],
                ["⌘,",        "開啟設定 · Settings"],
              ].map(([k, v], i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    padding: "2px 8px", minWidth: 56,
                    background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
                    fontFamily: fontMono, fontSize: 11, color: c.ink, letterSpacing: "0.08em",
                  }}>{k}</div>
                  <div style={{ fontSize: 12.5, color: c.inkSoft }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div>
          {/* Contact card */}
          <div style={{
            background: c.ink, color: c.paper,
            border: `1px solid ${c.ink}`, borderRadius: 2,
            padding: 24, marginBottom: 18, position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", right: -8, bottom: -30,
              fontFamily: fontHead, fontSize: 140,
              color: "rgba(231,228,222,0.05)", letterSpacing: "0.08em",
              lineHeight: 1, userSelect: "none", pointerEvents: "none",
            }}>援</div>

            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.ocher, letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 12 }}>
              CONTACT · 聯繫我們
            </div>
            <div style={{ fontFamily: fontHead, fontSize: 22, fontWeight: 500, letterSpacing: "0.04em", lineHeight: 1.4, marginBottom: 8 }}>
              找不到答案？<br />寫信給我們。
            </div>
            <div style={{ fontSize: 12.5, color: "rgba(231,228,222,0.7)", lineHeight: 1.7, marginBottom: 20 }}>
              平均回覆時間 <strong style={{ color: c.paper }}>3.8 小時</strong>。企業方案享 1 小時內優先回覆。
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 14px", background: c.vermillion, color: c.paper,
                border: "none", borderRadius: 2, cursor: "pointer",
                fontFamily: fontBody, fontSize: 13, fontWeight: 500, letterSpacing: "0.04em",
              }}>
                <Icon d={Icons.mail} size={14} />
                發起客服對話
                <span style={{ flex: 1 }} />
                <span>→</span>
              </button>
              <button style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 14px",
                background: "rgba(231,228,222,0.08)", color: c.paper,
                border: `1px solid rgba(231,228,222,0.2)`, borderRadius: 2, cursor: "pointer",
                fontFamily: fontBody, fontSize: 13, letterSpacing: "0.04em",
              }}>
                <Icon d={Icons.link} size={14} />
                加入 Slack 社群
                <span style={{ flex: 1 }} />
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.ocher, letterSpacing: "0.12em" }}>1,240 人</span>
              </button>
            </div>
          </div>

          {/* Recent tickets */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, marginBottom: 18 }}>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.inkHair}`, display: "flex", alignItems: "center" }}>
              <div style={{ fontFamily: fontHead, fontSize: 13, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                我的客服紀錄
              </div>
              <span style={{ flex: 1 }} />
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em" }}>
                {CONTACT_HISTORY.length} TICKETS
              </span>
            </div>
            {CONTACT_HISTORY.map((tk, i) => (
              <div key={tk.id} style={{
                padding: "12px 16px",
                borderBottom: i < CONTACT_HISTORY.length - 1 ? `1px solid ${c.inkHair}` : "none",
                cursor: "pointer",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>
                    #{tk.id}
                  </span>
                  <Chip t={t} tone={tk.status === "replied" ? "accent" : "muted"} dot={tk.status === "replied"}>
                    {tk.status === "replied" ? "待你回覆" : "已結案"}
                  </Chip>
                  <span style={{ flex: 1 }} />
                  <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.04em" }}>
                    {tk.at}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: c.ink, marginBottom: 3 }}>{tk.subj}</div>
                <div style={{ fontSize: 11, color: c.inkMuted }}>— {tk.by}</div>
              </div>
            ))}
          </div>

          {/* System status */}
          <div style={{
            background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
            padding: 18, marginBottom: 18,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <span style={{
                width: 8, height: 8, borderRadius: "50%",
                background: c.jade,
                boxShadow: `0 0 0 3px ${c.jade}22`,
              }} />
              <div style={{ fontFamily: fontHead, fontSize: 13, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                全系統運作正常
              </div>
              <span style={{ flex: 1 }} />
              <a style={{ fontSize: 11, color: c.vermillion, cursor: "pointer", letterSpacing: "0.04em" }}>status →</a>
            </div>
            {[
              { n: "核心平台",   up: "99.98%" },
              { n: "Agent API",  up: "99.92%" },
              { n: "MCP 同步",   up: "99.75%" },
            ].map((s, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "7px 0",
                borderTop: `1px solid ${c.inkHair}`,
              }}>
                <span style={{ fontSize: 12, color: c.inkSoft, flex: 1 }}>{s.n}</span>
                <div style={{ display: "flex", gap: 2 }}>
                  {Array(20).fill(0).map((_, j) => (
                    <span key={j} style={{
                      width: 3, height: 12,
                      background: (i === 2 && j === 14) ? c.ocher : c.jade,
                      borderRadius: 1, opacity: 0.85,
                    }} />
                  ))}
                </div>
                <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.04em", minWidth: 48, textAlign: "right" }}>
                  {s.up}
                </span>
              </div>
            ))}
          </div>

          {/* Resources */}
          <div style={{ background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 18 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 12 }}>
              MORE · 更多資源
            </div>
            {[
              { l: "API 文件",      sub: "Developer reference",   icon: Icons.code },
              { l: "開發者變更日誌", sub: "Changelog · 每週更新", icon: Icons.doc },
              { l: "Roadmap",       sub: "我們接下來要做什麼",    icon: Icons.target },
              { l: "功能建議",      sub: "提一個想法給我們",      icon: Icons.sparkle },
            ].map((r, i) => (
              <a key={i} style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "10px 0",
                borderTop: i > 0 ? `1px solid ${c.inkHair}` : "none",
                cursor: "pointer",
              }}>
                <Icon d={r.icon} size={14} style={{ color: c.inkMuted }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5, color: c.ink, fontWeight: 500 }}>{r.l}</div>
                  <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 1 }}>{r.sub}</div>
                </div>
                <span style={{ color: c.inkFaint, fontSize: 14 }}>→</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.InkHelpPage = InkHelpPage;
