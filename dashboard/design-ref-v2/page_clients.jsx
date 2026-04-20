// ZenOS v2 · Clients — Deal pipeline + Deal detail
const { useState: useClS } = React;

const DEAL_STAGES = [
  { k: "lead",     zh: "潛在客戶",  en: "Lead" },
  { k: "qualify",  zh: "需求訪談",  en: "Qualify" },
  { k: "demo",     zh: "Demo",     en: "Demo" },
  { k: "proposal", zh: "提案報價",  en: "Proposal" },
  { k: "won",      zh: "成交",     en: "Won" },
];

const DEALS = [
  { id: "d1", company: "Acme Corp",        contact: "Sarah Chen",   amount: 240000, stage: 3, next: "2026-04-22 複盤會議", owner: "Me",    hot: true },
  { id: "d2", company: "Naruvia",          contact: "林志豪",        amount: 120000, stage: 2, next: "2026-04-21 Demo",     owner: "品瑄", hot: false },
  { id: "d3", company: "Pacific Studios",  contact: "Mike Liu",     amount: 88000,  stage: 1, next: "需求確認會",           owner: "宗翰", hot: false },
  { id: "d4", company: "Hanabi Tech",      contact: "松田 優子",      amount: 320000, stage: 4, next: "合約簽署",             owner: "Me",    hot: true },
  { id: "d5", company: "Orbit Labs",       contact: "Daniel Wu",    amount: 54000,  stage: 0, next: "首次接觸",             owner: "品瑄", hot: false },
  { id: "d6", company: "Verde Foods",      contact: "陳怡君",        amount: 150000, stage: 2, next: "2026-04-23 Demo",     owner: "子豪", hot: false },
  { id: "d7", company: "Kyoto Digital",    contact: "田中 健",        amount: 72000,  stage: 3, next: "報價審核",             owner: "宗翰", hot: false },
];

function InkClientsPage({ t }) {
  const [openId, setOpenId] = useClS(null);
  if (openId) return <InkDealDetail t={t} deal={DEALS.find(d => d.id === openId)} onBack={() => setOpenId(null)} />;
  return <InkClientsList t={t} onOpen={setOpenId} />;
}

function InkClientsList({ t, onOpen }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [view, setView] = useClS("pipeline");
  const totalAmount = DEALS.reduce((a, d) => a + d.amount, 0);
  const activeCount = DEALS.filter(d => d.stage < 4).length;
  const wonCount = DEALS.filter(d => d.stage === 4).length;

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="CRM · 客戶" title="客戶" en="Clients"
        subtitle="所有銷售機會與聯絡人，支援 Pipeline 與列表檢視。"
        right={<div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ display: "flex", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2 }}>
            {[["pipeline", "Pipeline"], ["list", "列表"]].map(([k, l]) => (
              <button key={k} onClick={() => setView(k)} style={{
                padding: "5px 12px",
                background: view === k ? c.ink : "transparent",
                color: view === k ? c.paper : c.inkMuted,
                border: "none", borderRadius: 2, cursor: "pointer",
                fontFamily: fontBody, fontSize: 12, letterSpacing: "0.04em",
              }}>{l}</button>
            ))}
          </div>
          <Btn t={t} variant="ghost" icon={Icons.filter}>篩選</Btn>
          <Btn t={t} variant="seal" icon={Icons.plus}>新機會</Btn>
        </div>}
      />

      {/* Top KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}`, marginBottom: 24 }}>
        {[
          { k: "Pipeline 總額", v: "$" + (totalAmount / 1000).toFixed(0) + "k", sub: DEALS.length + " 個機會" },
          { k: "進行中",        v: activeCount.toString(),                       sub: "4 個本週到期" },
          { k: "本月成交",      v: wonCount.toString(),                          sub: "目標 6" },
          { k: "平均交易",      v: "$" + Math.round(totalAmount / DEALS.length / 1000) + "k", sub: "↑ 12% QoQ" },
        ].map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>{s.k}</div>
            <div style={{ fontFamily: fontHead, fontSize: 28, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {view === "pipeline" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
          {DEAL_STAGES.map((s, si) => {
            const col = DEALS.filter(d => d.stage === si);
            const sum = col.reduce((a, d) => a + d.amount, 0);
            return (
              <div key={s.k} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{
                  padding: "10px 12px", background: c.surface,
                  border: `1px solid ${c.inkHair}`, borderRadius: 2,
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span style={{ fontFamily: fontHead, fontSize: 13, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
                      {s.zh}
                    </span>
                    <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>{col.length}</span>
                  </div>
                  <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em", marginTop: 3 }}>
                    ${(sum / 1000).toFixed(0)}k · {s.en.toUpperCase()}
                  </div>
                </div>
                {col.map(d => (
                  <button key={d.id} onClick={() => onOpen(d.id)} style={{
                    padding: "12px 12px", background: c.surface,
                    border: `1px solid ${c.inkHair}`,
                    borderLeft: d.hot ? `2px solid ${c.vermillion}` : `1px solid ${c.inkHair}`,
                    borderRadius: 2, textAlign: "left",
                    cursor: "pointer", fontFamily: fontBody,
                    color: c.ink, transition: "all .12s",
                  }}
                    onMouseEnter={e => e.currentTarget.style.background = c.surfaceHi}
                    onMouseLeave={e => e.currentTarget.style.background = c.surface}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: "0.02em" }}>{d.company}</span>
                      {d.hot && <span style={{ fontFamily: fontMono, fontSize: 9, color: c.vermillion, letterSpacing: "0.1em" }}>HOT</span>}
                    </div>
                    <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>
                      ${(d.amount / 1000).toFixed(0)}k
                    </div>
                    <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 6 }}>{d.contact}</div>
                    <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, marginTop: 6, letterSpacing: "0.04em" }}>
                      {d.next}
                    </div>
                  </button>
                ))}
                {col.length === 0 && (
                  <div style={{
                    padding: 16, background: "transparent",
                    border: `1px dashed ${c.inkHair}`, borderRadius: 2,
                    textAlign: "center", fontSize: 11, color: c.inkFaint,
                  }}>空</div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 140px 100px 120px 180px 80px",
            gap: 12, padding: "10px 16px",
            borderBottom: `1px solid ${c.inkHairBold}`,
            fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
            letterSpacing: "0.18em", textTransform: "uppercase",
          }}>
            <span>公司 · 聯絡人</span><span>階段</span><span>金額</span><span>負責</span><span>下一步</span><span></span>
          </div>
          {DEALS.map(d => (
            <button key={d.id} onClick={() => onOpen(d.id)} style={{
              display: "grid", gridTemplateColumns: "1fr 140px 100px 120px 180px 80px",
              gap: 12, alignItems: "center", width: "100%",
              padding: "14px 16px", borderBottom: `1px solid ${c.inkHair}`,
              background: "transparent", border: "none",
              borderLeft: d.hot ? `2px solid ${c.vermillion}` : "2px solid transparent",
              color: c.ink, cursor: "pointer", textAlign: "left", fontFamily: fontBody,
            }}
              onMouseEnter={e => e.currentTarget.style.background = c.surfaceHi}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{d.company}</div>
                <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{d.contact}</div>
              </div>
              <Chip t={t} tone={d.stage === 4 ? "jade" : d.stage >= 3 ? "accent" : "muted"} dot>{DEAL_STAGES[d.stage].zh}</Chip>
              <span style={{ fontFamily: fontMono, fontSize: 13, color: c.ink }}>${(d.amount / 1000).toFixed(0)}k</span>
              <span style={{ fontSize: 12, color: c.inkMuted }}>{d.owner}</span>
              <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.04em" }}>{d.next}</span>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.vermillion, letterSpacing: "0.1em", textAlign: "right" }}>
                {d.hot ? "HOT" : ""}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Deal detail (second layer) ────────────────────────────────────────
function InkDealDetail({ t, deal, onBack }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [tab, setTab] = useClS("overview");

  return (
    <div style={{ padding: "32px 48px 60px", maxWidth: 1600 }}>
      <button onClick={onBack} style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        background: "transparent", border: "none", color: c.inkMuted,
        cursor: "pointer", fontFamily: fontBody, fontSize: 12,
        padding: "4px 8px 4px 0", marginBottom: 18,
      }}>
        <Icon d="M19 12H5M12 19l-7-7 7-7" size={14} /> 返回客戶
      </button>

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, marginBottom: 22 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
              DEAL · #{deal.id}
            </span>
            <Chip t={t} tone="accent" dot>{DEAL_STAGES[deal.stage].zh}</Chip>
            {deal.hot && <Chip t={t} tone="accent">HOT</Chip>}
          </div>
          <h1 style={{ fontFamily: fontHead, fontSize: 34, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.02em" }}>
            {deal.company}
          </h1>
          <div style={{ display: "flex", gap: 18, marginTop: 10, fontSize: 13, color: c.inkMuted }}>
            <span>聯絡人 · <span style={{ color: c.ink }}>{deal.contact}</span></span>
            <span>金額 · <span style={{ color: c.ink, fontFamily: fontMono }}>${(deal.amount / 1000).toFixed(0)}k</span></span>
            <span>負責 · <span style={{ color: c.ink }}>{deal.owner}</span></span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Btn t={t} variant="ghost" size="sm" icon={Icons.clock}>排程</Btn>
          <Btn t={t} variant="outline" size="sm" icon={Icons.spark}>Agent 建議</Btn>
          <Btn t={t} variant="ink" size="sm" icon={Icons.arrow}>推進階段</Btn>
        </div>
      </div>

      {/* Pipeline progress */}
      <div style={{
        display: "flex", alignItems: "center", gap: 4,
        padding: "12px 16px", background: c.surface,
        border: `1px solid ${c.inkHair}`, borderRadius: 2, marginBottom: 20,
      }}>
        {DEAL_STAGES.map((s, i) => {
          const done = i < deal.stage, cur = i === deal.stage;
          return (
            <React.Fragment key={i}>
              <div style={{
                padding: "4px 10px",
                fontFamily: fontBody, fontSize: 12,
                color: cur ? c.vermillion : done ? c.ink : c.inkFaint,
                fontWeight: cur ? 500 : 400, letterSpacing: "0.04em",
              }}>{s.zh}</div>
              {i < DEAL_STAGES.length - 1 && (
                <div style={{ flex: 1, height: 2, background: done ? c.ink : c.inkHair }} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: 20, borderBottom: `1px solid ${c.inkHair}` }}>
        {[["overview", "總覽"], ["activity", "活動"], ["commits", "承諾事項"], ["files", "附件"]].map(([k, l]) => (
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

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Agent debrief */}
          <div style={{
            background: c.surface, border: `1px solid ${c.inkHair}`,
            borderRadius: 2, padding: 20,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <Icon d={Icons.spark} size={13} style={{ color: c.vermillion }} />
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
                Agent 複盤摘要
              </span>
              <span style={{ flex: 1 }} />
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>04/18</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div>
                <div style={{ fontFamily: fontHead, fontSize: 12, color: c.ink, fontWeight: 500, marginBottom: 8, letterSpacing: "0.08em" }}>
                  關鍵決策
                </div>
                <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 12.5, color: c.inkSoft, lineHeight: 1.8 }}>
                  <li>確認 Q3 導入 ZenOS，先行 Pilot 一個部門。</li>
                  <li>由 Sarah 主導內部 alignment，4/25 前回覆。</li>
                </ul>
              </div>
              <div>
                <div style={{ fontFamily: fontHead, fontSize: 12, color: c.ink, fontWeight: 500, marginBottom: 8, letterSpacing: "0.08em" }}>
                  客戶顧慮
                </div>
                <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 12.5, color: c.inkSoft, lineHeight: 1.8 }}>
                  <li>權限設計與現有 SSO 整合。</li>
                  <li>資料遷移時程，希望 6 週內完成。</li>
                </ul>
              </div>
            </div>
            <div style={{
              marginTop: 14, padding: "10px 12px",
              background: c.vermSoft, border: `1px solid ${c.vermLine}`,
              borderRadius: 2, fontSize: 12.5, color: c.ink, lineHeight: 1.6,
            }}>
              <span style={{ fontFamily: fontMono, fontSize: 9, color: c.vermillion, letterSpacing: "0.16em", marginRight: 8 }}>階段建議</span>
              建議推進至「提案報價」階段。
            </div>
          </div>

          {/* Timeline */}
          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 14 }}>
              Activity · 近期動態
            </div>
            {[
              { t: "04/18 14:20", zh: "Demo 會議完成，Agent 自動複盤。", tag: "Demo" },
              { t: "04/15 09:00", zh: "發出試算報價單。",                 tag: "報價" },
              { t: "04/12 16:30", zh: "Sarah 提出 3 個技術疑問。",         tag: "訪談" },
              { t: "04/08",       zh: "首次接觸，安排 Demo。",             tag: "接觸" },
            ].map((a, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "110px 8px 1fr 80px",
                gap: 12, alignItems: "flex-start",
                padding: "11px 0",
                borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em", paddingTop: 3 }}>{a.t}</span>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.ink, marginTop: 6 }} />
                <span style={{ fontSize: 13, color: c.ink, lineHeight: 1.55 }}>{a.zh}</span>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkMuted, letterSpacing: "0.08em", textAlign: "right", paddingTop: 3 }}>{a.tag}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Side: commits + contact */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 18 }}>
            <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, marginBottom: 12, letterSpacing: "0.04em" }}>
              承諾事項
            </div>
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.18em", marginBottom: 6 }}>我方</div>
            {[
              { c: "寄出 SSO 整合規格", d: "04/22" },
              { c: "準備客製化報價",    d: "04/24" },
            ].map((x, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: `1px solid ${c.inkHair}`, fontSize: 12 }}>
                <span style={{ color: c.ink }}>{x.c}</span>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.vermillion }}>{x.d}</span>
              </div>
            ))}
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.18em", margin: "14px 0 6px" }}>客戶</div>
            {[{ c: "內部 alignment 回覆", d: "04/25" }].map((x, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 12 }}>
                <span style={{ color: c.ink }}>{x.c}</span>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkMuted }}>{x.d}</span>
              </div>
            ))}
          </div>

          <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 18 }}>
            <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, marginBottom: 12, letterSpacing: "0.04em" }}>
              聯絡人
            </div>
            {[
              { n: "Sarah Chen", r: "CTO · 決策者",   tone: "accent" },
              { n: "Mike Wang",  r: "IT Lead",       tone: "muted" },
            ].map((p, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: i < 1 ? `1px solid ${c.inkHair}` : "none" }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", background: p.tone === "accent" ? c.vermSoft : c.paperWarm, border: `1px solid ${p.tone === "accent" ? c.vermLine : c.inkHair}`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: fontHead, fontSize: 11, color: p.tone === "accent" ? c.vermillion : c.inkMuted, fontWeight: 500 }}>
                  {p.n[0]}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5, color: c.ink, fontWeight: 500 }}>{p.n}</div>
                  <div style={{ fontSize: 11, color: c.inkMuted }}>{p.r}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.InkClientsPage = InkClientsPage;
