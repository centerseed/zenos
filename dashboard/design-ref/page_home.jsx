// ZenOS v2 · Home (Today) page — morning report
function InkHomePage({ t, onGo, onOpenCmdK }) {
  const { c, fontHead, fontMono, fontBody } = t;

  const priorities = [
    { zh: "客戶 Acme 產品演示 follow-up",   en: "Acme follow-up",     due: "今日 16:00", tone: "accent" },
    { zh: "審查權限治理邊界案例",             en: "Review governance",  due: "今日",      tone: "ocher" },
    { zh: "重寫拖拉動效",                    en: "Drag perf rewrite",  due: "明日",      tone: "muted" },
  ];

  return (
    <div>
      <HeroToday t={t} />
      <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>

        <Section t={t} eyebrow="MORNING BRIEF · 晨報" title="晨報" en="Briefing"
          subtitle="每日早上 7:00 由 Agent 產生。本日焦點、Agent 提醒、會議節奏。"
        />

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 24, marginBottom: 48 }}>
          {/* Priorities */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 22 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
                Priorities · 本日重點
              </div>
              <button onClick={() => onGo?.("tasks")} style={{
                background: "transparent", border: "none", cursor: "pointer",
                fontFamily: fontMono, fontSize: 10, color: c.inkMuted, letterSpacing: "0.1em",
              }}>全部 →</button>
            </div>
            {priorities.map((p, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "flex-start", gap: 14,
                padding: "14px 0",
                borderBottom: i < priorities.length - 1 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <span style={{
                  fontFamily: fontMono, fontSize: 11, fontWeight: 500,
                  color: p.tone === "accent" ? c.vermillion : p.tone === "ocher" ? c.ocher : c.inkMuted,
                  letterSpacing: "0.08em", marginTop: 3, minWidth: 18,
                }}>{String(i + 1).padStart(2, "0")}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, color: c.ink, lineHeight: 1.5, fontFamily: fontBody }}>{p.zh}</div>
                  <div style={{ fontSize: 11, color: c.inkFaint, fontStyle: "italic", marginTop: 2 }}>{p.en}</div>
                </div>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: p.tone === "accent" ? c.vermillion : c.inkFaint, letterSpacing: "0.08em" }}>
                  {p.due}
                </span>
              </div>
            ))}
          </div>

          {/* Agent summary */}
          <div style={{
            background: c.paperWarm, border: `1px solid ${c.inkHair}`,
            borderRadius: 2, padding: 22,
            display: "flex", flexDirection: "column",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <Icon d={Icons.spark} size={13} style={{ color: c.vermillion }} />
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
                Agent Summary
              </span>
            </div>
            <p style={{
              fontFamily: fontBody, fontSize: 14, color: c.ink,
              margin: 0, lineHeight: 1.75, fontWeight: 400,
            }}>
              本週有 <span style={{ color: c.vermillion, fontWeight: 500 }}>3 項 P0 任務</span> 待處理，其中 Acme 演示需今日完成。後端有兩個阻塞集中在 Value Validation 相關 ADR，建議優先處理。
            </p>
            <div style={{ flex: 1 }} />
            <div style={{
              marginTop: 18, paddingTop: 14, borderTop: `1px solid ${c.inkHair}`,
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em" }}>
                07:24 · 閱讀約 30 秒
              </span>
              <button onClick={onOpenCmdK} style={{
                background: "transparent", border: `1px solid ${c.inkHair}`,
                padding: "4px 10px", borderRadius: 2, cursor: "pointer",
                fontFamily: fontBody, fontSize: 11, color: c.ink,
              }}>問 Agent →</button>
            </div>
          </div>

          {/* Schedule */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 22 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 16 }}>
              Schedule · 本日行程
            </div>
            {[
              { t: "09:00", end: "10:30", zh: "深度工作",   en: "Deep focus",   tone: "ink" },
              { t: "11:00", end: "11:30", zh: "Acme 會議", en: "Demo call",    tone: "accent" },
              { t: "14:00", end: "15:00", zh: "Code Review", en: "Code review", tone: "ink" },
              { t: "16:30", end: "17:00", zh: "每日回顧",   en: "Daily retro", tone: "muted" },
            ].map((b, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "70px 3px 1fr",
                gap: 14, alignItems: "flex-start",
                padding: "11px 0",
                borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.1em", paddingTop: 2 }}>
                  {b.t}<br /><span style={{ color: c.inkHair }}>{b.end}</span>
                </div>
                <div style={{
                  width: 2, background: b.tone === "accent" ? c.vermillion : b.tone === "muted" ? c.inkHair : c.ink,
                  alignSelf: "stretch",
                }} />
                <div>
                  <div style={{ fontFamily: fontBody, fontSize: 14, color: c.ink, fontWeight: 500, letterSpacing: "0.02em" }}>
                    {b.zh}
                  </div>
                  <div style={{ fontSize: 11, color: c.inkFaint, fontStyle: "italic", marginTop: 1 }}>{b.en}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.InkHomePage = InkHomePage;
