// ZenOS v2 · Projects — list + detail
const { useState: useProjS } = React;

const PROJECTS = [
  { id: "p1", code: "ZEN-24",  name: "ZenOS 2.0 產品發表",     desc: "Q2 全階段：工程、行銷、客戶成功串接的 launch。",
    owner: "品瑄", members: 7, tasks: 24, done: 13, docs: 8, due: "2026-05-15", health: "track",  color: "vermillion" },
  { id: "p2", code: "KG-07",   name: "Knowledge Graph v2",      desc: "重構向量索引、hybrid search、引用溯源體驗。",
    owner: "怡君", members: 4, tasks: 18, done: 11, docs: 5, due: "2026-05-02", health: "risk",   color: "ocher"     },
  { id: "p3", code: "CRM-11",  name: "CRM · Deal Autopilot",     desc: "從 Debrief 到自動 follow-up 的一整條 agent 流程。",
    owner: "宗翰", members: 3, tasks: 15, done: 4,  docs: 3, due: "2026-06-10", health: "track",  color: "jade"      },
  { id: "p4", code: "BRAND-02",name: "品牌視覺全面升級",        desc: "Zen Ink 設計語言正式上線，含網站、產品 shell、文件。",
    owner: "子豪", members: 5, tasks: 22, done: 9,  docs: 12,due: "2026-05-20", health: "track",  color: "ink"       },
  { id: "p5", code: "OPS-03",  name: "Q2 營運計畫",              desc: "OKR、預算、人力、節奏。",
    owner: "Me",   members: 2, tasks: 9,  done: 7,  docs: 6, due: "2026-04-30", health: "track",  color: "muted"     },
  { id: "p6", code: "INF-05",  name: "基礎設施遷移",             desc: "從 Supabase 雙區備援到 multi-region 讀寫。",
    owner: "怡君", members: 2, tasks: 11, done: 2,  docs: 2, due: "2026-06-30", health: "hold",   color: "muted"     },
];

const PROJ_HEALTH = {
  track: { tone: "jade",   zh: "順利" },
  risk:  { tone: "accent", zh: "風險" },
  hold:  { tone: "muted",  zh: "暫停" },
};

function InkProjectsPage({ t }) {
  const [openId, setOpenId] = useProjS(null);
  if (openId) return <InkProjectDetail t={t} proj={PROJECTS.find(p => p.id === openId)} onBack={() => setOpenId(null)} />;
  return <InkProjectsList t={t} onOpen={setOpenId} />;
}

function InkProjectsList({ t, onOpen }) {
  const { c, fontHead, fontMono, fontBody } = t;
  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="WORK · 專案" title="專案" en="Projects"
        subtitle="所有進行中的產品、營運、內容計畫。一個 project 對應一段真實的工作。"
        right={<div style={{ display: "flex", gap: 10 }}>
          <Btn t={t} variant="ghost" icon={Icons.filter}>篩選</Btn>
          <Btn t={t} variant="outline" icon={Icons.spark}>Agent 盤點</Btn>
          <Btn t={t} variant="seal" icon={Icons.plus}>新專案</Btn>
        </div>}
      />

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}`, marginBottom: 28 }}>
        {[
          { k: "進行中",       v: "6",   sub: "2 個高優先" },
          { k: "本週到期",     v: "3",   sub: "需要注意 · 1" },
          { k: "整體進度",     v: "58%", sub: "本季目標 70%" },
          { k: "待分派任務",   v: "12",  sub: "Agent 可協助" },
        ].map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>{s.k}</div>
            <div style={{ fontFamily: fontHead, fontSize: 28, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Project cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
        {PROJECTS.map(p => {
          const pct = Math.round((p.done / p.tasks) * 100);
          const h = PROJ_HEALTH[p.health];
          const accent = p.color === "vermillion" ? c.vermillion : p.color === "ocher" ? c.ocher : p.color === "jade" ? c.jade : p.color === "ink" ? c.ink : c.inkMuted;
          return (
            <button key={p.id} onClick={() => onOpen(p.id)} style={{
              padding: 0, background: c.surface,
              border: `1px solid ${c.inkHair}`, borderRadius: 2,
              textAlign: "left", cursor: "pointer",
              fontFamily: fontBody, color: c.ink,
              transition: "all .15s", overflow: "hidden",
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = c.inkHairBold; e.currentTarget.style.background = c.surfaceHi; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = c.inkHair; e.currentTarget.style.background = c.surface; }}>
              <div style={{ padding: "18px 20px 16px", borderLeft: `3px solid ${accent}` }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 14, marginBottom: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                      <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.16em" }}>{p.code}</span>
                      <Chip t={t} tone={h.tone} dot>{h.zh}</Chip>
                    </div>
                    <div style={{ fontFamily: fontHead, fontSize: 17, fontWeight: 500, color: c.ink, letterSpacing: "0.02em", lineHeight: 1.35 }}>
                      {p.name}
                    </div>
                    <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 6, lineHeight: 1.55 }}>
                      {p.desc}
                    </div>
                  </div>
                  <div style={{
                    width: 36, height: 36, borderRadius: "50%",
                    background: c.vermSoft, border: `1px solid ${c.vermLine}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontFamily: fontHead, fontSize: 12, color: c.vermillion, fontWeight: 500,
                  }}>{p.owner[0]}</div>
                </div>

                {/* progress bar */}
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
                    <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em", textTransform: "uppercase" }}>
                      進度 · {p.done}/{p.tasks}
                    </span>
                    <span style={{ fontFamily: fontMono, fontSize: 11, color: c.ink, fontWeight: 500 }}>{pct}%</span>
                  </div>
                  <div style={{ height: 3, background: c.inkHair, position: "relative", overflow: "hidden" }}>
                    <div style={{ position: "absolute", inset: 0, width: `${pct}%`, background: accent }} />
                  </div>
                </div>

                <div style={{
                  marginTop: 14, paddingTop: 12,
                  borderTop: `1px solid ${c.inkHair}`,
                  display: "flex", gap: 18, fontSize: 11, color: c.inkMuted,
                }}>
                  <span><span style={{ color: c.inkFaint, marginRight: 4 }}>成員</span>{p.members}</span>
                  <span><span style={{ color: c.inkFaint, marginRight: 4 }}>任務</span>{p.tasks}</span>
                  <span><span style={{ color: c.inkFaint, marginRight: 4 }}>文件</span>{p.docs}</span>
                  <span style={{ flex: 1 }} />
                  <span style={{ fontFamily: fontMono, color: p.health === "risk" ? c.vermillion : c.inkMuted, letterSpacing: "0.04em" }}>
                    {p.due}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Project detail (second layer) ─────────────────────────────────────
function InkProjectDetail({ t, proj, onBack }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [tab, setTab] = useProjS("overview");
  const pct = Math.round((proj.done / proj.tasks) * 100);
  const h = PROJ_HEALTH[proj.health];
  const accent = proj.color === "vermillion" ? c.vermillion : proj.color === "ocher" ? c.ocher : proj.color === "jade" ? c.jade : proj.color === "ink" ? c.ink : c.inkMuted;

  return (
    <div style={{ padding: "32px 48px 60px", maxWidth: 1600 }}>
      <button onClick={onBack} style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        background: "transparent", border: "none", color: c.inkMuted,
        cursor: "pointer", fontFamily: fontBody, fontSize: 12,
        padding: "4px 8px 4px 0", marginBottom: 18,
      }}>
        <Icon d="M19 12H5M12 19l-7-7 7-7" size={14} /> 返回專案
      </button>

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, marginBottom: 22 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em" }}>
              PROJECT · {proj.code}
            </span>
            <Chip t={t} tone={h.tone} dot>{h.zh}</Chip>
          </div>
          <h1 style={{ fontFamily: fontHead, fontSize: 34, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.02em" }}>
            {proj.name}
          </h1>
          <p style={{ fontSize: 13, color: c.inkMuted, margin: "10px 0 0", maxWidth: 700, lineHeight: 1.7 }}>{proj.desc}</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Btn t={t} variant="ghost" size="sm" icon={Icons.doc}>Brief</Btn>
          <Btn t={t} variant="outline" size="sm" icon={Icons.spark}>Agent 建議</Btn>
          <Btn t={t} variant="ink" size="sm" icon={Icons.plus}>新任務</Btn>
        </div>
      </div>

      {/* Metrics strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr) 2fr", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}`, marginBottom: 24 }}>
        {[
          { k: "負責人",  v: proj.owner, sub: `+ ${proj.members - 1} 成員` },
          { k: "任務",    v: `${proj.done}/${proj.tasks}`, sub: `${pct}% 完成` },
          { k: "文件",    v: proj.docs.toString(), sub: "最新 · 昨天" },
          { k: "截止",    v: proj.due.slice(5), sub: "2026 · " + proj.due.slice(0, 4) },
        ].map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "14px 16px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 6 }}>{s.k}</div>
            <div style={{ fontFamily: fontHead, fontSize: 20, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{s.sub}</div>
          </div>
        ))}
        <div style={{ background: c.surface, padding: "14px 20px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>
            進度軌跡
          </div>
          <div style={{ height: 4, background: c.inkHair, position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", inset: 0, width: `${pct}%`, background: accent }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>START 03/01</span>
            <span style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500 }}>{pct}%</span>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>{proj.due}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: 20, borderBottom: `1px solid ${c.inkHair}` }}>
        {[["overview", "總覽"], ["tasks", "任務"], ["docs", "文件"], ["members", "成員"], ["timeline", "時程"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} style={{
            padding: "10px 18px", background: "transparent", border: "none",
            borderBottom: tab === k ? `2px solid ${c.vermillion}` : "2px solid transparent",
            marginBottom: -1, cursor: "pointer",
            fontFamily: fontBody, fontSize: 13,
            color: tab === k ? c.ink : c.inkMuted,
            fontWeight: tab === k ? 500 : 400, letterSpacing: "0.04em",
          }}>{l}</button>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Milestones */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 14 }}>
              Milestones · 里程碑
            </div>
            {[
              { d: true,  zh: "規格與範疇鎖定",       when: "03/15" },
              { d: true,  zh: "核心功能開發 v1",      when: "04/10" },
              { d: false, zh: "內部 Dogfood 一週",    when: "04/28", cur: true },
              { d: false, zh: "公開 Beta",            when: "05/05" },
              { d: false, zh: "GA · 正式發表",         when: "05/15" },
            ].map((m, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "20px 1fr 90px",
                gap: 12, alignItems: "center",
                padding: "11px 0", borderBottom: i < 4 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <span style={{
                  width: 14, height: 14, borderRadius: "50%",
                  border: `1.5px solid ${m.d ? c.ink : m.cur ? c.vermillion : c.inkHair}`,
                  background: m.d ? c.ink : m.cur ? c.vermSoft : "transparent",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: c.paper, fontFamily: fontMono, fontSize: 8,
                }}>{m.d ? "✓" : ""}</span>
                <span style={{
                  fontSize: 13, lineHeight: 1.5,
                  color: m.d ? c.inkMuted : c.ink,
                  fontWeight: m.cur ? 500 : 400,
                }}>{m.zh}</span>
                <span style={{
                  fontFamily: fontMono, fontSize: 10,
                  color: m.cur ? c.vermillion : c.inkFaint,
                  letterSpacing: "0.08em", textAlign: "right",
                }}>{m.when}</span>
              </div>
            ))}
          </div>

          {/* Recent activity */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 14 }}>
              Activity · 近期動態
            </div>
            {[
              { t: "04/18", who: "Agent",  zh: "彙整本週任務完成情況並產出週報草稿。" },
              { t: "04/17", who: "怡君",   zh: "關閉 4 個 review 中的任務。" },
              { t: "04/15", who: "品瑄",   zh: "更新 Beta 名單與時程文件。" },
              { t: "04/12", who: "宗翰",   zh: "新增「API 速率限制」任務。" },
            ].map((a, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "72px 1fr",
                gap: 14, padding: "10px 0",
                borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>{a.t}</span>
                <div style={{ fontSize: 12.5, color: c.ink, lineHeight: 1.55 }}>
                  <span style={{ fontWeight: 500 }}>{a.who}</span> · {a.zh}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Related docs */}
          <div style={{ background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 16 }}>
            <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, letterSpacing: "0.04em", marginBottom: 10 }}>
              文件
            </div>
            {[
              "產品規格 v2.3",
              "Beta Test Plan",
              "發表主 Keynote",
              "QA 測試報告",
            ].map((d, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 0", borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none",
                fontSize: 12.5, color: c.ink, cursor: "pointer",
              }}>
                <Icon d={Icons.doc} size={12} style={{ color: c.inkFaint }} />
                <span style={{ flex: 1 }}>{d}</span>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>04/{12 + i}</span>
              </div>
            ))}
          </div>

          {/* Members */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 16 }}>
            <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, letterSpacing: "0.04em", marginBottom: 10 }}>
              成員
            </div>
            {[
              { n: proj.owner, r: "PM · Owner", tone: "accent" },
              { n: "怡君",      r: "Engineer", tone: "muted" },
              { n: "宗翰",      r: "Engineer", tone: "muted" },
              { n: "子豪",      r: "Designer", tone: "muted" },
            ].map((p, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none" }}>
                <div style={{
                  width: 26, height: 26, borderRadius: "50%",
                  background: p.tone === "accent" ? c.vermSoft : c.paperWarm,
                  border: `1px solid ${p.tone === "accent" ? c.vermLine : c.inkHair}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: fontHead, fontSize: 11,
                  color: p.tone === "accent" ? c.vermillion : c.inkMuted, fontWeight: 500,
                }}>{p.n[0]}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5, color: c.ink, fontWeight: 500 }}>{p.n}</div>
                  <div style={{ fontSize: 10.5, color: c.inkMuted }}>{p.r}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.InkProjectsPage = InkProjectsPage;
