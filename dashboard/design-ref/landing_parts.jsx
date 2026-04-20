// ZenOS · Landing — shared shell parts (Nav / Footer / FeatureCanvas placeholders)

function LandingNav({ t, active, onChange }) {
  const { c, fontMono, fontHead } = t;
  return (
    <nav style={{
      position: "sticky", top: 0, zIndex: 50,
      padding: "18px 40px", display: "flex", alignItems: "center", gap: 40,
      background: `${c.paper}ee`, backdropFilter: "blur(12px)",
      borderBottom: `1px solid ${c.inkHair}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          width: 26, height: 26, background: c.vermillion,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: fontHead, color: c.paper, fontSize: 15, letterSpacing: 0,
          borderRadius: 1,
        }}>禪</div>
        <div style={{
          fontFamily: fontHead, fontSize: 16, color: c.ink,
          letterSpacing: "0.18em", fontWeight: 500,
        }}>ZenOS</div>
        <div style={{
          fontFamily: fontMono, fontSize: 9, color: c.inkFaint,
          letterSpacing: "0.24em", textTransform: "uppercase",
          padding: "3px 8px", border: `1px solid ${c.inkHair}`, marginLeft: 4,
        }}>Beta</div>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", gap: 28 }}>
        {["功能", "流程", "信念", "定價", "日誌"].map((x, i) => (
          <a key={i} style={{
            fontFamily: fontHead, fontSize: 13, color: c.inkSoft,
            letterSpacing: "0.16em", cursor: "pointer",
          }}>{x}</a>
        ))}
      </div>
      <button style={{
        padding: "9px 22px", background: c.ink, color: c.paper,
        border: "none", borderRadius: 2, cursor: "pointer",
        fontFamily: "inherit", fontSize: 12, letterSpacing: "0.16em",
        textTransform: "uppercase",
      }}>加入 Waitlist</button>
    </nav>
  );
}

function LandingFooter({ t }) {
  const { c, fontMono, fontHead } = t;
  return (
    <footer style={{
      padding: "80px 80px 40px", borderTop: `1px solid ${c.inkHair}`,
      background: c.paperWarm, color: c.inkMuted,
    }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 60 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
            <div style={{
              width: 22, height: 22, background: c.vermillion,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: fontHead, color: c.paper, fontSize: 13,
            }}>禪</div>
            <div style={{ fontFamily: fontHead, fontSize: 14, color: c.ink, letterSpacing: "0.18em" }}>ZenOS</div>
          </div>
          <p style={{ fontSize: 12, lineHeight: 1.9, maxWidth: 320, margin: 0, fontFamily: fontHead, letterSpacing: "0.04em" }}>
            為獨行者與小隊而造的知識工作台。<br />
            一方畫紙，收束散亂思緒。
          </p>
        </div>
        {[
          { h: "產品", items: ["功能地圖", "路線圖", "更新日誌", "定價"] },
          { h: "團隊", items: ["關於我們", "信念書", "職缺", "媒體包"] },
          { h: "聯繫", items: ["support@zenos.tw", "Twitter / X", "台北 · 信義"] },
        ].map((col, i) => (
          <div key={i}>
            <div style={{
              fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
              letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 18,
            }}>{col.h}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {col.items.map((x, j) => (
                <a key={j} style={{ fontFamily: fontHead, fontSize: 13, color: c.inkSoft, cursor: "pointer", letterSpacing: "0.04em" }}>{x}</a>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{
        maxWidth: 1200, margin: "60px auto 0", paddingTop: 24,
        borderTop: `1px solid ${c.inkHair}`,
        display: "flex", justifyContent: "space-between",
        fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em",
      }}>
        <span>© 2026 ZENOS · 台北 · 穀雨版</span>
        <span>靜 · 觀 · 作 · 成</span>
      </div>
    </footer>
  );
}

// Placeholder illustrative canvases (no real screenshots yet)
function FeatureCanvas({ t, variant, kind }) {
  const { c, fontHead, fontMono } = t;
  const accent = variant === "vermillion" ? c.vermillion : variant === "jade" ? c.jade : c.ink;

  if (kind === "knowledge") {
    // knowledge-graph nodes
    const nodes = [
      { x: 50, y: 40, r: 7, label: "客戶 · 青山" },
      { x: 180, y: 80, r: 10, label: "春分提案" },
      { x: 300, y: 60, r: 6, label: "會議 04/20" },
      { x: 120, y: 180, r: 8, label: "設計稿 v3" },
      { x: 260, y: 200, r: 7, label: "合約 · 第二期" },
      { x: 380, y: 160, r: 9, label: "下一季度" },
      { x: 420, y: 280, r: 6, label: "回訪 06/12" },
      { x: 180, y: 290, r: 7, label: "付款條件" },
    ];
    const edges = [[0,1],[1,2],[1,3],[3,4],[4,5],[2,5],[4,7],[5,6],[7,3]];
    return (
      <div style={{
        aspectRatio: "1.15 / 1", background: c.surface,
        border: `1px solid ${c.inkHair}`, position: "relative", overflow: "hidden",
      }}>
        <div style={{ position: "absolute", top: 16, left: 20, fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.24em" }}>
          KNOWLEDGE · 知識地圖
        </div>
        <div style={{ position: "absolute", top: 16, right: 20, fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.24em" }}>
          28 節點 · 42 連結
        </div>
        <svg viewBox="0 0 500 340" style={{ width: "100%", height: "100%" }}>
          {edges.map(([a, b], i) => (
            <line key={i} x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
              stroke={c.inkHairBold} strokeWidth="0.6" />
          ))}
          {nodes.map((n, i) => (
            <g key={i}>
              <circle cx={n.x} cy={n.y} r={n.r} fill={i === 1 ? accent : c.ink} opacity={i === 1 ? 1 : 0.85} />
              {i === 1 && <circle cx={n.x} cy={n.y} r={n.r + 6} fill="none" stroke={accent} strokeWidth="0.5" opacity="0.5" />}
              <text x={n.x + n.r + 6} y={n.y + 3} fontFamily={fontHead} fontSize="9" fill={c.inkSoft} letterSpacing="0.08em">{n.label}</text>
            </g>
          ))}
        </svg>
      </div>
    );
  }

  if (kind === "agent") {
    return (
      <div style={{
        aspectRatio: "1.15 / 1", background: c.surface,
        border: `1px solid ${c.inkHair}`, padding: 28,
        display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.24em" }}>
            QUIET AGENT · 靜默筆記
          </div>
          <div style={{
            fontFamily: fontMono, fontSize: 9, color: c.jade,
            letterSpacing: "0.18em",
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <span style={{ width: 5, height: 5, background: c.jade, borderRadius: "50%" }} />
            背景運作中
          </div>
        </div>
        {[
          { t: "07:42", h: "歸檔了昨日與青山會議紀要", meta: "5 項決定 · 3 個待辦已建立" },
          { t: "09:15", h: "發現「合約 v2」未被任何人簽核", meta: "建議 ping @思明" },
          { t: "10:28", h: "替客戶王總複盤，草稿已備妥", meta: "1 頁 · 三段重點" },
          { t: "14:03", h: "例會前 15 分，整理了議程", meta: "上週未竟 2 項已標註" },
        ].map((x, i) => (
          <div key={i} style={{
            padding: "12px 14px", background: c.paper,
            borderLeft: `2px solid ${i === 0 ? accent : c.inkHair}`,
            display: "flex", gap: 16,
          }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em", minWidth: 36 }}>
              {x.t}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: fontHead, fontSize: 12, color: c.ink, marginBottom: 3, letterSpacing: "0.04em" }}>
                {x.h}
              </div>
              <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.1em" }}>
                {x.meta}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // rhythm — calendar / wheel
  return (
    <div style={{
      aspectRatio: "1.15 / 1", background: c.surface,
      border: `1px solid ${c.inkHair}`, padding: 28, position: "relative",
    }}>
      <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.24em", marginBottom: 6 }}>
        RHYTHM · 本週節律
      </div>
      <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, letterSpacing: "0.08em", marginBottom: 20 }}>
        穀雨 · Week 16
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6, marginBottom: 20 }}>
        {["一","二","三","四","五","六","日"].map((d, i) => (
          <div key={i} style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, textAlign: "center", letterSpacing: "0.1em" }}>{d}</div>
        ))}
        {[0.6, 0.85, 0.45, 0.95, 0.7, 0.2, 0.15].map((v, i) => (
          <div key={i} style={{
            aspectRatio: "1", background: c.paper, border: `1px solid ${c.inkHair}`,
            position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", left: 0, right: 0, bottom: 0,
              height: `${v * 100}%`,
              background: i === 3 ? accent : c.ink, opacity: i === 3 ? 1 : 0.75,
            }} />
            <div style={{
              position: "absolute", top: 4, left: 6,
              fontFamily: fontMono, fontSize: 9,
              color: v > 0.6 ? c.paper : c.ink,
              letterSpacing: "0.04em",
              mixBlendMode: "difference",
            }}>{15 + i}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 24 }}>
        {[
          { l: "專注時數", v: "24.5h" },
          { l: "完成任務", v: "18 / 23" },
          { l: "深工次數", v: "7" },
        ].map((s, i) => (
          <div key={i} style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 10 }}>
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.16em", marginBottom: 4 }}>{s.l}</div>
            <div style={{ fontFamily: fontHead, fontSize: 18, color: c.ink, letterSpacing: "0.04em" }}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { LandingNav, LandingFooter, FeatureCanvas });
