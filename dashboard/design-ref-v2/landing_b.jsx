// ZenOS · Landing — Variant B (精量企業 · structured SaaS)
// Multi-column, credibility-forward, metrics + logos + product pane.
// Same ink palette but tighter, more "enterprise".

function LandingB({ t }) {
  const { c, fontHead, fontBody, fontMono } = t;

  return (
    <div style={{ background: c.paper, color: c.ink, fontFamily: fontBody }}>
      <LandingNav t={t} />

      {/* ── Hero ─────────────────────────────────────── */}
      <section style={{
        padding: "80px 80px 60px",
        display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 60,
        alignItems: "center",
        borderBottom: `1px solid ${c.inkHair}`,
      }}>
        <div>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 10,
            padding: "6px 14px", border: `1px solid ${c.inkHairBold}`,
            fontFamily: fontMono, fontSize: 10, color: c.inkSoft,
            letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 32,
            background: c.surface,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: c.vermillion }} />
            Private Beta · 邀請制 · 穀雨 2026
          </div>
          <h1 style={{
            fontFamily: fontHead, fontSize: 68, fontWeight: 500,
            color: c.ink, margin: 0, lineHeight: 1.15, letterSpacing: "0.02em",
          }}>
            團隊的知識，<br />
            應該是<span style={{ color: c.vermillion }}>共同的資產</span>。
          </h1>
          <p style={{
            fontFamily: fontBody, fontSize: 17, color: c.inkMuted,
            lineHeight: 1.75, maxWidth: 520, margin: "32px 0 0", letterSpacing: "0.02em",
          }}>
            ZenOS 把散落在訊息、文件、會議中的資料，收束成一方結構化的畫紙。
            讓獨行者有依據，讓小隊伍有節奏，讓決定者有全貌。
          </p>
          <div style={{ display: "flex", gap: 14, marginTop: 40, alignItems: "center" }}>
            <button style={{
              padding: "14px 28px", background: c.ink, color: c.paper,
              border: "none", borderRadius: 2, cursor: "pointer",
              fontFamily: "inherit", fontSize: 13, letterSpacing: "0.14em",
              textTransform: "uppercase", fontWeight: 500,
            }}>加入 Waitlist</button>
            <button style={{
              padding: "14px 24px", background: "transparent", color: c.ink,
              border: `1px solid ${c.inkHairBold}`, borderRadius: 2, cursor: "pointer",
              fontFamily: "inherit", fontSize: 13, letterSpacing: "0.14em",
              textTransform: "uppercase", fontWeight: 500,
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span style={{ fontSize: 11 }}>▶</span> 觀看演示
            </button>
          </div>
          <div style={{ marginTop: 28, display: "flex", gap: 28, fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em", textTransform: "uppercase" }}>
            <span>✓ 30 天免費</span>
            <span>✓ 不需信用卡</span>
            <span>✓ 資料可隨時匯出</span>
          </div>
        </div>

        {/* Hero product pane */}
        <HeroProductPane t={t} />
      </section>

      {/* ── Metrics band ─────────────────────────── */}
      <section style={{ padding: "80px 80px", borderBottom: `1px solid ${c.inkHair}` }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 2fr", gap: 80, alignItems: "center" }}>
          <div>
            <div style={{
              fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
              letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 18,
            }}>在 ZenOS 上</div>
            <h2 style={{
              fontFamily: fontHead, fontSize: 36, fontWeight: 500,
              color: c.ink, margin: 0, letterSpacing: "0.04em", lineHeight: 1.3,
            }}>
              少即是多。<br />
              讓數字自己說話。
            </h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0 }}>
            {[
              { v: "43%", l: "會議時間減少", sub: "相較於前三個月" },
              { v: "2.4×", l: "決定落地速度", sub: "從討論到執行" },
              { v: "98%", l: "文件可被找到", sub: "語意檢索命中率" },
              { v: "12min", l: "日均整理時間", sub: "由 Agent 代勞" },
            ].map((m, i) => (
              <div key={i} style={{
                padding: "0 24px",
                borderLeft: i > 0 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <div style={{
                  fontFamily: fontHead, fontSize: 44, fontWeight: 500, color: c.ink,
                  letterSpacing: "0.02em", marginBottom: 8, lineHeight: 1,
                }}>{m.v}</div>
                <div style={{
                  fontSize: 13, color: c.inkSoft, marginBottom: 4,
                  letterSpacing: "0.04em", fontFamily: fontHead,
                }}>{m.l}</div>
                <div style={{
                  fontFamily: fontMono, fontSize: 9, color: c.inkFaint,
                  letterSpacing: "0.12em",
                }}>{m.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 使用流程 (4 columns) ─────────────────────── */}
      <section style={{ padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`, background: c.paperWarm }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 60 }}>
            <div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 14 }}>
                ZenOS 的一日
              </div>
              <h2 style={{ fontFamily: fontHead, fontSize: 44, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.04em", lineHeight: 1.25, maxWidth: 680 }}>
                晨起一張晨報，收工一次盤點。
              </h2>
              <p style={{ fontSize: 14, color: c.inkMuted, lineHeight: 1.85, margin: "18px 0 0", maxWidth: 560, letterSpacing: "0.02em" }}>
                一切步驟，皆站在同一張知識地圖上。每個 Agent、每段對話、每份文件，共享一套脈絡。
              </p>
            </div>
            <a style={{ fontFamily: fontMono, fontSize: 11, color: c.vermillion, letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer" }}>
              查看完整產品導覽 →
            </a>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0 }}>
            {[
              { n: "07:00", zh: "晨", en: "BRIEFING",  t: "晨報 · 今日焦點", d: "Agent 於清晨備妥：焦點三事、新進訊息、今日會議節奏。一覽便知當日方向。" },
              { n: "日間",  zh: "作", en: "WORKSPACE", t: "任務與專案並行",  d: "Tasks、Projects、Clients、Docs 同處一方畫紙。所有工作的脈絡，皆互相連結。" },
              { n: "對話",  zh: "問", en: "AGENT",     t: "與 Agent 共筆",   d: "每份文件、每個客戶、每場會議旁，都有一方 Agent 工作區——且 Agent 之間共享同一份記憶。" },
              { n: "17:30", zh: "觀", en: "DEBRIEF",   t: "收工的回看",      d: "一天之末，Agent 整理今日所成、明日所待。決定與脈絡，皆寫回共同的知識地圖。" },
            ].map((s, i) => (
              <div key={i} style={{
                padding: "32px 28px 32px 28px",
                background: c.surface, border: `1px solid ${c.inkHair}`,
                borderLeft: i === 0 ? `1px solid ${c.inkHair}` : "none",
                position: "relative",
              }}>
                <div style={{
                  fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
                  letterSpacing: "0.2em", marginBottom: 24,
                }}>{s.n} · {s.en}</div>
                <div style={{
                  fontFamily: fontHead, fontSize: 42, fontWeight: 500, color: c.vermillion,
                  letterSpacing: "0.04em", marginBottom: 18, lineHeight: 1,
                }}>{s.zh}</div>
                <h3 style={{
                  fontFamily: fontHead, fontSize: 19, fontWeight: 500, color: c.ink,
                  margin: "0 0 14px", letterSpacing: "0.04em",
                }}>{s.t}</h3>
                <p style={{
                  fontSize: 13, color: c.inkMuted, lineHeight: 1.8,
                  margin: 0, letterSpacing: "0.02em",
                }}>{s.d}</p>
              </div>
            ))}
          </div>

          {/* Shared substrate — knowledge graph line */}
          <div style={{
            marginTop: 0,
            background: c.surface,
            border: `1px solid ${c.inkHair}`, borderTop: "none",
            padding: "28px 36px",
            display: "grid", gridTemplateColumns: "180px 1fr 1fr", gap: 40,
            alignItems: "center",
          }}>
            <div>
              <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.26em", marginBottom: 6 }}>
                SUBSTRATE · 底層
              </div>
              <div style={{ fontFamily: fontHead, fontSize: 18, color: c.vermillion, letterSpacing: "0.08em" }}>
                共享知識地圖
              </div>
            </div>
            <p style={{ fontFamily: fontHead, fontSize: 14, color: c.inkSoft, margin: 0, lineHeight: 1.85, letterSpacing: "0.04em" }}>
              所有步驟、所有 Agent、所有對話，皆寫入同一張知識地圖。
              Context 不因對話結束而消失，Agent 切換亦不需重新說明。
            </p>
            <svg viewBox="0 0 360 60" style={{ width: "100%", height: 60 }}>
              <line x1="20" y1="30" x2="340" y2="30" stroke={c.inkHairBold} strokeWidth="0.6" strokeDasharray="2 3" />
              {[40, 120, 200, 280, 340].map((x, i) => (
                <g key={i}>
                  <circle cx={x} cy="30" r={i === 4 ? 3 : 5} fill={i === 2 ? c.vermillion : c.ink} opacity={i === 4 ? 0.5 : 1} />
                  {i < 4 && [[x-12, 14], [x+12, 46], [x-14, 48], [x+14, 12]][i] && (
                    <line x1={x} y1="30" x2={[x-14, x+14, x-16, x+16][i]} y2={[14, 46, 48, 12][i]} stroke={c.inkHair} strokeWidth="0.5" />
                  )}
                </g>
              ))}
              {[[28, 14], [112, 48], [188, 48], [296, 12], [212, 14], [128, 14]].map(([x, y], i) => (
                <circle key={`sat-${i}`} cx={x} cy={y} r="2" fill={c.inkMuted} opacity="0.6" />
              ))}
            </svg>
          </div>
        </div>
      </section>

      {/* ── 功能亮點 · 3 產品 slabs (alternating) ─────── */}
      {[
        { idx: "功能 · 01", zh: "知識地圖", en: "Knowledge Graph", kind: "knowledge",
          title: "一切關聯，皆在紙上。",
          body: "客戶、專案、文件、對話不再各自為政。ZenOS 替你連起脈絡——從一點可回溯來處，從一處可望見全局。語意檢索 98% 命中率。",
          bullets: ["自動連結實體與概念", "語意搜索，不靠關鍵字", "可視化團隊知識的流向"],
          reverse: false, accent: "vermillion",
        },
        { idx: "功能 · 02", zh: "靜默 Agent", en: "Quiet Agent", kind: "agent",
          title: "AI 不喧嘩，只做事。",
          body: "Agent 於背景運作：歸檔會議紀要、提醒未覆郵件、為客戶複盤草擬下一步。你只需在恰當時機，翻閱它留下的筆記。",
          bullets: ["日均代工 12 分鐘", "信得過的決策紀錄", "關鍵時才出聲"],
          reverse: true, accent: "ink",
        },
        { idx: "功能 · 03", zh: "節律儀表", en: "Rhythm Dashboard", kind: "rhythm",
          title: "日有日的工，月有月的成。",
          body: "以節氣與週期為脈，ZenOS 幫你維繫工作的呼吸：專注、休整、盤點、再出發。紀律不是約束，是自由的基石。",
          bullets: ["專注與休整自動追蹤", "月度盤點報告", "個人與團隊節律同步"],
          reverse: false, accent: "jade",
        },
      ].map((f, i) => (
        <section key={i} style={{
          padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`,
          background: i % 2 === 1 ? c.paperWarm : c.paper,
        }}>
          <div style={{
            maxWidth: 1200, margin: "0 auto",
            display: "grid",
            gridTemplateColumns: f.reverse ? "1fr 1fr" : "1fr 1fr",
            gap: 80, alignItems: "center",
          }}>
            <div style={{ order: f.reverse ? 2 : 1 }}>
              <div style={{
                fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
                letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 16,
              }}>{f.idx}</div>
              <div style={{
                fontFamily: fontHead, fontSize: 13, color: c.vermillion,
                letterSpacing: "0.2em", marginBottom: 20,
              }}>{f.zh} · {f.en}</div>
              <h3 style={{
                fontFamily: fontHead, fontSize: 38, fontWeight: 500, color: c.ink,
                margin: "0 0 22px", letterSpacing: "0.04em", lineHeight: 1.3,
              }}>{f.title}</h3>
              <p style={{
                fontSize: 15, color: c.inkMuted, lineHeight: 1.85,
                margin: "0 0 24px", letterSpacing: "0.02em",
              }}>{f.body}</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {f.bullets.map((b, j) => (
                  <div key={j} style={{
                    display: "flex", alignItems: "center", gap: 12,
                    fontSize: 13, color: c.inkSoft, letterSpacing: "0.02em",
                  }}>
                    <span style={{
                      width: 14, height: 1, background: c.vermillion,
                    }} />
                    {b}
                  </div>
                ))}
              </div>
              <a style={{
                display: "inline-block", marginTop: 32,
                fontFamily: fontMono, fontSize: 11, color: c.vermillion,
                letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer",
                borderBottom: `1px solid ${c.vermLine}`, paddingBottom: 4,
              }}>了解更多 →</a>
            </div>
            <div style={{ order: f.reverse ? 1 : 2 }}>
              <FeatureCanvas t={t} variant={f.accent} kind={f.kind} />
            </div>
          </div>
        </section>
      ))}

      {/* ── Testimonial ─────────────────────────── */}
      <section style={{
        padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`,
        background: c.paper,
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{
            fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
            letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 40, textAlign: "center",
          }}>
            實踐者的話 · TESTIMONIAL
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0 }}>
            {[
              {
                q: "過去團隊會議常落在『我們上次說了什麼』。ZenOS 的 Agent 在每場會前整理好脈絡，我們開始能真正往前走。",
                n: "林思明", t: "青山設計 · 創辦人",
              },
              {
                q: "作為一個人的工作室，最怕的就是客戶資料四散。ZenOS 把一切收束成一方畫紙，我終於能好好睡覺。",
                n: "王雲帆", t: "獨立策略顧問",
              },
              {
                q: "不吵、不亮、不要求你注意它。這是我用過最少打擾，卻最有存在感的工具。",
                n: "陳若水", t: "Atelier 若水 · 主理人",
              },
            ].map((x, i) => (
              <div key={i} style={{
                padding: "0 36px",
                borderLeft: i > 0 ? `1px solid ${c.inkHair}` : "none",
              }}>
                <div style={{
                  fontFamily: fontHead, fontSize: 40, color: c.vermillion,
                  lineHeight: 1, marginBottom: 18,
                }}>「</div>
                <p style={{
                  fontFamily: fontHead, fontSize: 15, color: c.ink,
                  lineHeight: 1.9, margin: "0 0 28px", letterSpacing: "0.03em", fontWeight: 400,
                }}>{x.q}</p>
                <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 14 }}>
                  <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, marginBottom: 2, letterSpacing: "0.06em" }}>{x.n}</div>
                  <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em" }}>{x.t}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ─────────────────────────── */}
      <section style={{
        padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 60 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 16 }}>定價 · 穀雨初版</div>
            <h2 style={{ fontFamily: fontHead, fontSize: 44, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.04em" }}>
              簡潔，如其名。
            </h2>
            <p style={{ fontFamily: fontHead, fontSize: 14, color: c.inkMuted, marginTop: 18, letterSpacing: "0.06em" }}>
              價格尚在思忖中。正式開放時將寄一封信給你。
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24, maxWidth: 1000, margin: "0 auto" }}>
            {[
              { h: "獨行 · Solo", sub: "為個人工作者", price: "待定", meta: "預計月費 · 親民", feats: ["個人知識地圖", "靜默 Agent · 標準", "節律儀表 · 個人"], cta: "Waitlist" },
              { h: "小隊 · Team", sub: "5–20 人團隊", price: "待定", meta: "預計以人數計費", feats: ["共享知識地圖", "Agent · 團隊版", "節律儀表 · 團隊同步", "自訂工作流"], cta: "Waitlist", highlight: true },
              { h: "工坊 · Studio", sub: "20+ 人組織", price: "商議", meta: "含實施顧問", feats: ["企業級部署", "自訂整合", "專屬顧問", "安全與合規"], cta: "聯繫我們" },
            ].map((p, i) => (
              <div key={i} style={{
                padding: 32, background: p.highlight ? c.ink : c.surface,
                border: `1px solid ${p.highlight ? c.ink : c.inkHair}`,
                color: p.highlight ? c.paper : c.ink,
                position: "relative",
              }}>
                {p.highlight && (
                  <div style={{
                    position: "absolute", top: -10, right: 24,
                    padding: "4px 10px", background: c.vermillion, color: c.paper,
                    fontFamily: fontMono, fontSize: 9, letterSpacing: "0.2em",
                  }}>推薦</div>
                )}
                <div style={{ fontFamily: fontHead, fontSize: 22, fontWeight: 500, letterSpacing: "0.06em", marginBottom: 4 }}>{p.h}</div>
                <div style={{ fontFamily: fontMono, fontSize: 10, opacity: 0.7, letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 28 }}>{p.sub}</div>
                <div style={{ fontFamily: fontHead, fontSize: 44, fontWeight: 500, lineHeight: 1, letterSpacing: "0.02em" }}>{p.price}</div>
                <div style={{ fontFamily: fontMono, fontSize: 10, opacity: 0.7, letterSpacing: "0.12em", marginTop: 6, marginBottom: 28 }}>{p.meta}</div>
                <div style={{ borderTop: `1px solid ${p.highlight ? "rgba(244,239,228,0.15)" : c.inkHair}`, paddingTop: 20, marginBottom: 24 }}>
                  {p.feats.map((f, j) => (
                    <div key={j} style={{ fontSize: 12.5, lineHeight: 2, letterSpacing: "0.02em", opacity: 0.85, fontFamily: "inherit" }}>
                      · {f}
                    </div>
                  ))}
                </div>
                <button style={{
                  width: "100%", padding: "12px 0",
                  background: p.highlight ? c.vermillion : "transparent",
                  color: p.highlight ? c.paper : c.ink,
                  border: `1px solid ${p.highlight ? c.vermillion : c.inkHairBold}`,
                  borderRadius: 2, cursor: "pointer",
                  fontFamily: "inherit", fontSize: 12, letterSpacing: "0.16em", textTransform: "uppercase", fontWeight: 500,
                }}>
                  {p.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Manifesto (compact) ─────────────── */}
      <section style={{
        padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`,
        background: c.ink, color: c.paper, textAlign: "center",
      }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: "rgba(244,239,228,0.5)", letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 28 }}>MANIFESTO · 信念書</div>
          <h2 style={{
            fontFamily: fontHead, fontSize: 30, fontWeight: 400, color: c.paper,
            margin: 0, letterSpacing: "0.06em", lineHeight: 1.9,
          }}>
            工具本該退到背景，讓思考走到前臺。<br />
            真正的效率，不是更快地做更多，<br />
            而是清楚地知道何者必作、何者可捨。<br />
            <span style={{ color: c.vermillion }}>願你以禪心，做實事。</span>
          </h2>
        </div>
      </section>

      {/* ── Final CTA ─────────────── */}
      <section style={{
        padding: "110px 80px", textAlign: "center",
        borderBottom: `1px solid ${c.inkHair}`,
      }}>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 20 }}>此刻，便是起點</div>
        <h2 style={{ fontFamily: fontHead, fontSize: 52, fontWeight: 500, color: c.ink, margin: "0 0 28px", letterSpacing: "0.05em" }}>
          加入內測名單
        </h2>
        <p style={{ fontFamily: fontHead, fontSize: 15, color: c.inkMuted, maxWidth: 500, margin: "0 auto 44px", lineHeight: 1.85, letterSpacing: "0.03em" }}>
          名額有限。我們會親自篩選、親自邀請、親自陪伴每一位使用者。
        </p>
        <div style={{
          display: "flex", gap: 0, maxWidth: 460, margin: "0 auto",
          border: `1px solid ${c.inkHairBold}`, borderRadius: 2, background: c.surface,
        }}>
          <input placeholder="name@company.tw" style={{
            flex: 1, padding: "14px 18px", background: "transparent",
            border: "none", outline: "none",
            fontFamily: fontBody, fontSize: 14, color: c.ink,
          }} />
          <button style={{
            padding: "0 28px", background: c.ink, color: c.paper,
            border: "none", cursor: "pointer",
            fontFamily: "inherit", fontSize: 12, letterSpacing: "0.18em", textTransform: "uppercase",
          }}>加入</button>
        </div>
      </section>

      <LandingFooter t={t} />
    </div>
  );
}

// Hero product pane — stacked product mock
function HeroProductPane({ t }) {
  const { c, fontHead, fontMono } = t;
  return (
    <div style={{ position: "relative", aspectRatio: "1.05 / 1" }}>
      {/* Back card — knowledge graph hint */}
      <div style={{
        position: "absolute", top: 0, right: 0, width: "78%", height: "78%",
        background: c.surface, border: `1px solid ${c.inkHair}`,
        boxShadow: `0 20px 40px -20px rgba(20,18,16,0.2)`,
      }}>
        <div style={{ padding: 18, display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${c.inkHair}` }}>
          <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em" }}>KNOWLEDGE · 知識地圖</span>
          <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em" }}>28 / 42</span>
        </div>
        <svg viewBox="0 0 400 260" style={{ width: "100%", height: "calc(100% - 40px)" }}>
          {[[60,60,160,100],[160,100,280,80],[160,100,100,180],[100,180,240,200],[240,200,330,160],[240,200,150,250]].map(([x1,y1,x2,y2],i) => (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={c.inkHairBold} strokeWidth="0.6" />
          ))}
          {[[60,60,6],[160,100,9,true],[280,80,5],[100,180,7],[240,200,8],[330,160,6],[150,250,5]].map(([cx,cy,r,hl],i) => (
            <circle key={i} cx={cx} cy={cy} r={r} fill={hl ? c.vermillion : c.ink} opacity={hl ? 1 : 0.8} />
          ))}
        </svg>
      </div>

      {/* Front card — agent activity */}
      <div style={{
        position: "absolute", bottom: 0, left: 0, width: "62%",
        background: c.paper, border: `1px solid ${c.inkHairBold}`,
        boxShadow: `0 24px 50px -16px rgba(20,18,16,0.25)`,
        padding: 18,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em" }}>AGENT · 今日</span>
          <span style={{
            fontFamily: fontMono, fontSize: 9, color: c.jade,
            letterSpacing: "0.16em",
            display: "flex", alignItems: "center", gap: 5,
          }}>
            <span style={{ width: 5, height: 5, background: c.jade, borderRadius: "50%" }} />運作中
          </span>
        </div>
        {[
          { t: "07:42", h: "歸檔昨日會議紀要", m: "5 項決定" },
          { t: "09:15", h: "提醒 · 合約 v2 未簽", m: "→ @思明" },
          { t: "10:28", h: "王總複盤草稿備妥", m: "3 段重點" },
        ].map((x, i) => (
          <div key={i} style={{
            padding: "9px 10px", marginBottom: 6,
            background: c.surface,
            borderLeft: `2px solid ${i === 0 ? c.vermillion : c.inkHair}`,
            display: "flex", gap: 12,
          }}>
            <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.1em", minWidth: 32 }}>{x.t}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: fontHead, fontSize: 11, color: c.ink, letterSpacing: "0.04em" }}>{x.h}</div>
              <div style={{ fontFamily: fontMono, fontSize: 8.5, color: c.inkFaint, letterSpacing: "0.08em", marginTop: 2 }}>{x.m}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Seal stamp */}
      <div style={{
        position: "absolute", top: 10, left: 10,
        width: 54, height: 54,
        background: c.vermillion, color: c.paper,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        fontFamily: fontHead, fontSize: 11, letterSpacing: "0.06em",
        lineHeight: 1.2, borderRadius: 2,
        boxShadow: `0 6px 14px -4px rgba(156,46,31,0.4)`,
        transform: "rotate(-4deg)",
      }}>
        <div>ZEN</div><div>OS</div>
      </div>
    </div>
  );
}

window.LandingB = LandingB;
