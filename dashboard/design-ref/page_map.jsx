// ZenOS v2 · Knowledge Map (原點呈現 structure, Zen Ink styling)
const { useState: useMS } = React;

function InkMapPage({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [selected, setSelected] = useMS("n_nebula");
  const [hover, setHover] = useMS(null);

  const nodes = [
    { id: "n_nebula",   type: "project", label: "Project Nebula",   x: 420, y: 240, r: 28, meta: "12 個任務 · 3 個阻塞" },
    { id: "n_q2okr",    type: "plan",    label: "Q2 OKR",           x: 620, y: 160, r: 22, meta: "5 項 Key Results" },
    { id: "n_acme",     type: "client",  label: "Acme Corp",        x: 260, y: 120, r: 22, meta: "Deal $240k · Stage 3" },
    { id: "n_gov",      type: "domain",  label: "Governance",       x: 180, y: 320, r: 22, meta: "8 條規則" },
    { id: "n_crm",      type: "domain",  label: "CRM",              x: 260, y: 430, r: 22, meta: "42 筆聯絡人" },
    { id: "n_content",  type: "project", label: "Content Pipeline", x: 620, y: 380, r: 22, meta: "4 篇草稿" },
    { id: "n_brief",    type: "doc",     label: "Briefing 04/19",   x: 520, y: 70,  r: 16, meta: "自動產生" },
    { id: "n_amy",      type: "person",  label: "怡君 Amy",         x: 380, y: 120, r: 14, meta: "Frontend Lead" },
    { id: "n_tim",      type: "person",  label: "宗翰 Tim",         x: 540, y: 280, r: 14, meta: "Backend / AI" },
    { id: "n_val",      type: "domain",  label: "Value Validation", x: 720, y: 280, r: 18, meta: "ADR-014" },
  ];
  const edges = [
    ["n_nebula", "n_q2okr"], ["n_nebula", "n_amy"], ["n_nebula", "n_tim"],
    ["n_nebula", "n_gov"],   ["n_nebula", "n_crm"], ["n_crm", "n_acme"],
    ["n_q2okr", "n_brief"],  ["n_content", "n_nebula"], ["n_val", "n_q2okr"],
    ["n_acme", "n_amy"],     ["n_tim", "n_val"],    ["n_gov", "n_crm"],
  ];
  const nm = Object.fromEntries(nodes.map(n => [n.id, n]));
  const sel = nm[selected] || nodes[0];

  const typeColor = {
    project: c.vermillion, plan: c.ocher, client: c.jade,
    domain: c.ink, doc: c.inkMuted, person: c.seal,
  };
  const typeLabel = {
    project: "PROJECT", plan: "PLAN", client: "CLIENT",
    domain: "DOMAIN", doc: "DOC", person: "PERSON",
  };

  return (
    <div style={{ padding: "40px 48px 48px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="CONTEXT · 知識" title="知識地圖" en="Knowledge Map"
        subtitle="所有專案、客戶、文件之間的關係。點擊節點展開 context。"
        right={<div style={{ display: "flex", gap: 10 }}>
          <Chip t={t} tone="muted">{nodes.length} 節點 · {edges.length} 關聯</Chip>
          <Btn t={t} variant="ghost" icon={Icons.filter}>濾鏡</Btn>
          <Btn t={t} variant="outline" icon={Icons.spark}>Agent 詢問此圖</Btn>
        </div>}
      />

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 340px",
        gap: 16, height: "calc(100vh - 260px)", minHeight: 560,
      }}>
        {/* Canvas */}
        <div style={{
          position: "relative",
          background: `radial-gradient(circle at 50% 40%, ${c.surfaceHi}, ${c.paper} 72%)`,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          overflow: "hidden",
        }}>
          {/* grid pattern */}
          <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
            <defs>
              <pattern id="mapgrid" width="32" height="32" patternUnits="userSpaceOnUse">
                <path d="M 32 0 L 0 0 0 32" fill="none" stroke={c.inkHair} strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#mapgrid)" />
          </svg>

          {/* Graph */}
          <svg viewBox="0 0 900 520" style={{ width: "100%", height: "100%", position: "relative" }}>
            {edges.map(([a, b], i) => {
              const na = nm[a], nb = nm[b];
              const isActive = a === selected || b === selected;
              return (
                <line key={i} x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
                  stroke={isActive ? c.vermillion : c.inkHairBold}
                  strokeWidth={isActive ? 1.4 : 0.8}
                  strokeDasharray={isActive ? "0" : "3 3"}
                  opacity={isActive ? 0.8 : 0.55} />
              );
            })}
            {nodes.map(n => {
              const isSel = n.id === selected;
              const isHov = n.id === hover;
              const color = typeColor[n.type] || c.ink;
              return (
                <g key={n.id} onClick={() => setSelected(n.id)}
                   onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}
                   style={{ cursor: "pointer" }}>
                  {isSel && (
                    <circle cx={n.x} cy={n.y} r={n.r + 8} fill="none"
                            stroke={c.vermillion} strokeWidth={1} opacity={0.4} />
                  )}
                  <circle cx={n.x} cy={n.y} r={n.r}
                          fill={isSel ? c.vermillion : (isHov ? c.surfaceHi : c.surface)}
                          stroke={isSel ? c.vermillion : color}
                          strokeWidth={isSel ? 1.6 : 1.1} />
                  {n.type === "project" && (
                    <circle cx={n.x} cy={n.y} r={n.r - 6} fill="none"
                            stroke={isSel ? c.paper : color} strokeWidth={0.8} opacity={0.6} />
                  )}
                  <text x={n.x} y={n.y + n.r + 14} textAnchor="middle"
                        fill={isSel ? c.ink : c.inkMuted}
                        fontSize={11} fontFamily={fontBody}
                        fontWeight={isSel ? 500 : 400}>
                    {n.label}
                  </text>
                  <text x={n.x} y={n.y + n.r + 26} textAnchor="middle"
                        fill={c.inkFaint}
                        fontSize={9} fontFamily={fontMono}
                        letterSpacing="0.08em">
                    {typeLabel[n.type]}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Legend bottom-left */}
          <div style={{
            position: "absolute", bottom: 14, left: 14,
            display: "flex", gap: 10, flexWrap: "wrap",
            fontFamily: fontMono, fontSize: 10,
            color: c.inkFaint, letterSpacing: "0.08em",
          }}>
            {Object.entries(typeLabel).map(([k, v]) => (
              <span key={k} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: typeColor[k] }} />
                {v}
              </span>
            ))}
          </div>

          {/* Zoom controls */}
          <div style={{
            position: "absolute", bottom: 14, right: 14,
            display: "flex", flexDirection: "column", gap: 4,
          }}>
            {["+", "−", "⌖"].map((s, i) => (
              <button key={i} style={{
                width: 28, height: 28,
                background: c.surface, border: `1px solid ${c.inkHair}`,
                borderRadius: 2, color: c.inkMuted, fontSize: 13,
                cursor: "pointer", fontFamily: fontMono,
              }}>{s}</button>
            ))}
          </div>
        </div>

        {/* Inspector */}
        <div style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          padding: 18, overflow: "auto",
          display: "flex", flexDirection: "column", gap: 14,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%",
              background: c.vermSoft, border: `1px solid ${c.vermLine}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              color: c.vermillion, fontSize: 14, fontFamily: fontHead, fontWeight: 500,
            }}>●</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                {sel.type}
              </div>
              <div style={{ fontFamily: fontHead, fontSize: 17, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>
                {sel.label}
              </div>
              <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 2 }}>{sel.meta}</div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <Btn t={t} variant="ghost" size="sm" icon={Icons.arrow}>開啟</Btn>
            <Btn t={t} variant="ghost" size="sm" icon={Icons.link}>複製連結</Btn>
          </div>

          {/* AI summary */}
          <div style={{
            background: c.paperWarm,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            padding: 12,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <Icon d={Icons.spark} size={12} style={{ color: c.vermillion }} />
              <span style={{
                fontFamily: fontMono, fontSize: 10,
                color: c.inkFaint, letterSpacing: "0.12em", textTransform: "uppercase",
              }}>
                Agent Summary
              </span>
            </div>
            <p style={{ fontSize: 12, lineHeight: 1.6, color: c.ink, margin: 0 }}>
              Nebula 是本季最密集的專案節點，與 Q2 OKR、Governance、CRM 三個領域都有連接。目前有
              <span style={{ color: c.ocher, fontWeight: 500 }}> 3 項阻塞任務 </span>
              集中在後端，建議優先處理 Value Validation 相關 ADR。
            </p>
          </div>

          {/* Relations */}
          <div>
            <div style={{
              fontFamily: fontMono, fontSize: 10,
              color: c.inkFaint, letterSpacing: "0.12em", textTransform: "uppercase",
              marginBottom: 8,
            }}>
              相關 · Relations
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {edges.filter(e => e[0] === selected || e[1] === selected).map(([a, b], i) => {
                const other = nm[a === selected ? b : a];
                return (
                  <button key={i} onClick={() => setSelected(other.id)} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "6px 8px", borderRadius: 2,
                    background: "transparent", border: "none",
                    color: c.ink, cursor: "pointer", fontSize: 12,
                    textAlign: "left", fontFamily: fontBody,
                  }}
                    onMouseEnter={e => e.currentTarget.style.background = c.surfaceHi}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: typeColor[other.type] }} />
                    <span style={{ flex: 1 }}>{other.label}</span>
                    <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>
                      {other.type}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Recent activity */}
          <div>
            <div style={{
              fontFamily: fontMono, fontSize: 10,
              color: c.inkFaint, letterSpacing: "0.12em", textTransform: "uppercase",
              marginBottom: 8,
            }}>
              近期活動
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { t: "Tim 新增了 ADR-014",   d: "2 小時前" },
                { t: "Agent 生成 Briefing", d: "5 小時前" },
                { t: "Amy 關閉任務 t5",      d: "昨天" },
              ].map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, fontSize: 12 }}>
                  <span style={{ width: 4, height: 4, borderRadius: "50%", background: c.inkFaint, marginTop: 7 }} />
                  <span style={{ color: c.ink, flex: 1 }}>{a.t}</span>
                  <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>{a.d}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.InkMapPage = InkMapPage;
