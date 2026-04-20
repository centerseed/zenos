// ZenOS v2 · Docs — tree + detail
const { useState: useDocS } = React;

const DOC_TREE = [
  { g: "個人", items: [
    { id: "d1",  n: "今週 · Barry",            u: "04/19", tag: "weekly",  pin: true  },
    { id: "d2",  n: "2026 Q2 個人 OKR",          u: "04/10", tag: "plan",    pin: false },
    { id: "d3",  n: "Reading List · LLM Ops",    u: "04/05", tag: "note",    pin: false },
  ]},
  { g: "團隊", items: [
    { id: "d4",  n: "團隊工作守則 v2",           u: "04/17", tag: "rule",    pin: true  },
    { id: "d5",  n: "Design System · Zen Ink",    u: "04/15", tag: "design",  pin: true  },
    { id: "d6",  n: "Engineering Weekly 04/16",   u: "04/16", tag: "weekly",  pin: false },
    { id: "d7",  n: "招募 JD · Senior Full-stack",u: "04/08", tag: "hr",      pin: false },
  ]},
  { g: "專案 · ZenOS 2.0", items: [
    { id: "d8",  n: "產品規格 v2.3",              u: "04/18", tag: "spec",    pin: true  },
    { id: "d9",  n: "Beta Test Plan",             u: "04/14", tag: "plan",    pin: false },
    { id: "d10", n: "發表主 Keynote",              u: "04/11", tag: "slides",  pin: false },
    { id: "d11", n: "QA 測試報告",                u: "04/17", tag: "qa",      pin: false },
  ]},
  { g: "專案 · KG v2", items: [
    { id: "d12", n: "Knowledge Graph 架構",        u: "04/16", tag: "spec",    pin: false },
    { id: "d13", n: "Hybrid Search Benchmark",     u: "04/13", tag: "research",pin: false },
  ]},
];

const DOC_FLAT = DOC_TREE.flatMap(g => g.items.map(it => ({ ...it, g: g.g })));

function InkDocsPage({ t }) {
  const [selected, setSelected] = useDocS(DOC_FLAT[0]?.id);
  const doc = DOC_FLAT.find(d => d.id === selected) || DOC_FLAT[0];
  return <InkDocsWorkspace t={t} doc={doc} selected={selected} onSelect={setSelected} />;
}

function InkDocsWorkspace({ t, doc, selected, onSelect }) {
  const { c, fontHead, fontMono, fontBody } = t;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr 320px", height: "100vh", background: c.paper }}>
      {/* Left · tree */}
      <aside style={{
        borderRight: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
        padding: "24px 16px 16px",
        overflowY: "auto",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
              Docs
            </div>
            <div style={{ fontFamily: fontHead, fontSize: 18, fontWeight: 500, color: c.ink, letterSpacing: "0.04em", marginTop: 2 }}>
              文件
            </div>
          </div>
          <Btn t={t} variant="ink" size="sm" icon={Icons.plus}>新</Btn>
        </div>

        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "7px 10px", marginBottom: 14,
          background: c.surface, border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
        }}>
          <Icon d={Icons.search} size={12} style={{ color: c.inkFaint }} />
          <input placeholder="搜尋文件…" style={{
            flex: 1, background: "transparent", border: "none", outline: "none",
            fontFamily: fontBody, fontSize: 12, color: c.ink,
          }} />
        </div>

        {/* Pinned */}
        <div style={{
          fontFamily: fontMono, fontSize: 9,
          color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase",
          padding: "0 4px 8px", display: "flex", alignItems: "center", gap: 8,
        }}>
          <span>Pinned</span>
          <div style={{ flex: 1, height: 1, background: c.inkHair }} />
        </div>
        {DOC_FLAT.filter(d => d.pin).map(d => (
          <button key={d.id} onClick={() => onSelect(d.id)} style={{
            display: "flex", alignItems: "center", gap: 8, width: "100%",
            padding: "6px 8px", background: selected === d.id ? c.surface : "transparent",
            border: "none", borderLeft: selected === d.id ? `2px solid ${c.vermillion}` : "2px solid transparent",
            cursor: "pointer", textAlign: "left", color: c.ink,
            fontFamily: fontBody, fontSize: 12.5, marginBottom: 2,
          }}>
            <span style={{ color: c.vermillion, fontSize: 9 }}>●</span>
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.n}</span>
          </button>
        ))}

        {/* Groups */}
        {DOC_TREE.map(grp => (
          <div key={grp.g} style={{ marginTop: 18 }}>
            <div style={{
              fontFamily: fontMono, fontSize: 9,
              color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase",
              padding: "0 4px 8px", display: "flex", alignItems: "center", gap: 8,
            }}>
              <span>{grp.g}</span>
              <div style={{ flex: 1, height: 1, background: c.inkHair }} />
              <span style={{ color: c.inkFaint }}>{grp.items.length}</span>
            </div>
            {grp.items.map(d => {
              const active = selected === d.id;
              return (
                <button key={d.id} onClick={() => onSelect(d.id)} style={{
                  display: "grid", gridTemplateColumns: "12px 1fr auto",
                  alignItems: "center", gap: 8, width: "100%",
                  padding: "6px 8px",
                  background: active ? c.surface : "transparent",
                  border: "none",
                  borderLeft: active ? `2px solid ${c.vermillion}` : "2px solid transparent",
                  cursor: "pointer", textAlign: "left",
                  color: active ? c.ink : c.inkSoft,
                  fontFamily: fontBody, fontSize: 12.5, marginBottom: 1,
                }}>
                  <Icon d={Icons.doc} size={11} style={{ color: c.inkFaint }} />
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.n}</span>
                  <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint }}>{d.u}</span>
                </button>
              );
            })}
          </div>
        ))}
      </aside>

      {/* Center · doc view */}
      <div style={{ overflowY: "auto", padding: "40px 64px 80px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
            {doc.g} · {doc.tag}
          </div>
          <h1 style={{ fontFamily: fontHead, fontSize: 36, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.02em", lineHeight: 1.2 }}>
            {doc.n}
          </h1>
          <div style={{ display: "flex", gap: 16, marginTop: 14, fontSize: 12, color: c.inkMuted }}>
            <span>作者 · <span style={{ color: c.ink }}>Barry</span></span>
            <span>更新 · <span style={{ color: c.ink, fontFamily: fontMono }}>04/{doc.u.slice(3)}</span></span>
            <span>協作 · <span style={{ color: c.ink }}>3 人</span></span>
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 16, paddingBottom: 20, borderBottom: `1px solid ${c.inkHair}` }}>
            <Btn t={t} variant="ghost" size="sm" icon={Icons.spark}>Agent 改寫</Btn>
            <Btn t={t} variant="ghost" size="sm" icon={Icons.link}>引用</Btn>
            <Btn t={t} variant="ghost" size="sm" icon={Icons.users}>分享</Btn>
          </div>

          {/* Body */}
          <div style={{ fontSize: 14.5, color: c.ink, lineHeight: 1.85, fontFamily: fontBody }}>
            <p style={{ marginTop: 28 }}>
              本週是 ZenOS 2.0 發表前的關鍵階段。整體進度目前落在 <b>58%</b>，
              比起預期略慢一週，但主要延遲集中在 Knowledge Graph 的向量索引重構，
              其餘工作流正常推進。
            </p>

            <h2 style={{ fontFamily: fontHead, fontSize: 20, fontWeight: 500, color: c.ink, letterSpacing: "0.04em", marginTop: 36, marginBottom: 12 }}>
              一、本週重點
            </h2>
            <ul style={{ margin: "0 0 24px", paddingLeft: 22 }}>
              <li>完成 Beta 名單確認（48 人，預計 4/28 啟動 dogfood）。</li>
              <li>行銷素材：主 Keynote、部落格長文、案例研究同步收斂中。</li>
              <li>QA 已完成 P0/P1 bug 的修復，剩餘 5 個 P2 本週清完。</li>
            </ul>

            <h2 style={{ fontFamily: fontHead, fontSize: 20, fontWeight: 500, color: c.ink, letterSpacing: "0.04em", marginTop: 36, marginBottom: 12 }}>
              二、風險與應對
            </h2>
            <div style={{
              padding: "14px 16px", background: c.vermSoft,
              border: `1px solid ${c.vermLine}`, borderRadius: 2,
              marginBottom: 24,
            }}>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.vermillion, letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 6 }}>
                注意事項
              </div>
              <div style={{ fontSize: 13.5, color: c.ink, lineHeight: 1.7 }}>
                KG v2 的 index rebuild 預估工時上修一週，建議將 Beta 時間從 04/28 順延至 05/02，整體 GA 時程不變。
              </div>
            </div>

            <h2 style={{ fontFamily: fontHead, fontSize: 20, fontWeight: 500, color: c.ink, letterSpacing: "0.04em", marginTop: 36, marginBottom: 12 }}>
              三、下週計畫
            </h2>
            <ol style={{ margin: "0 0 24px", paddingLeft: 22 }}>
              <li>完成 KG v2 index rebuild 與回歸測試。</li>
              <li>啟動 Beta（含 onboarding 簡訊、影片與客服 playbook）。</li>
              <li>行銷物料最後審查：Keynote、主視覺、新聞稿。</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Right · AI rail + outline */}
      <aside style={{
        borderLeft: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
        padding: "24px 20px",
        overflowY: "auto",
        display: "flex", flexDirection: "column", gap: 16,
      }}>
        <div>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
            大綱
          </div>
          {["一、本週重點", "二、風險與應對", "三、下週計畫"].map((h, i) => (
            <div key={i} style={{
              padding: "6px 8px", borderLeft: i === 0 ? `2px solid ${c.vermillion}` : "2px solid transparent",
              fontSize: 12.5, color: i === 0 ? c.ink : c.inkMuted,
              fontWeight: i === 0 ? 500 : 400, cursor: "pointer",
            }}>{h}</div>
          ))}
        </div>

        <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Icon d={Icons.spark} size={12} style={{ color: c.vermillion }} />
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
              Agent 建議
            </span>
          </div>
          <div style={{
            padding: "12px 14px", background: c.surface,
            border: `1px solid ${c.inkHair}`, borderRadius: 2,
            fontSize: 12.5, color: c.ink, lineHeight: 1.7,
          }}>
            第二段風險描述可再精簡。要我把「注意事項」轉成更中性的語氣嗎？
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            <Btn t={t} variant="ghost" size="sm">改寫</Btn>
            <Btn t={t} variant="ghost" size="sm">忽略</Btn>
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 16 }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
            引用 · 來源
          </div>
          {[
            { n: "ZenOS 2.0 · 產品規格 v2.3", t: "spec" },
            { n: "KG v2 · 架構",              t: "spec" },
            { n: "Beta Test Plan",            t: "plan" },
          ].map((r, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "7px 0", borderBottom: i < 2 ? `1px solid ${c.inkHair}` : "none",
              fontSize: 12, color: c.ink, cursor: "pointer",
            }}>
              <Icon d={Icons.link} size={11} style={{ color: c.inkFaint }} />
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.n}</span>
              <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint }}>{r.t}</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

window.InkDocsPage = InkDocsPage;
