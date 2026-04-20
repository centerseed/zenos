// ZenOS · Landing — Variant C (AI-native · command-first)
// Hero = giant prompt bar, scrolling example prompts, agent log as content.
// Ink palette but sharper, more monospace, terminal-adjacent.

function LandingC({ t }) {
  const { c, fontHead, fontBody, fontMono } = t;
  const [promptIdx, setPromptIdx] = React.useState(0);
  const prompts = [
    "幫我歸檔與青山的所有會議紀要，整理成時間軸。",
    "王總的合約有哪些未完成項？列給我看。",
    "下週四的例會，替我準備議程與上週延續事項。",
    "把過去三個月客戶反饋，分類為五個主題。",
    "提醒我，穀雨那週要完成春分提案的第二版。",
  ];
  React.useEffect(() => {
    const id = setInterval(() => setPromptIdx((i) => (i + 1) % prompts.length), 3200);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ background: c.paper, color: c.ink, fontFamily: fontBody }}>
      <LandingNav t={t} />

      {/* ── Hero · giant prompt ───────────────────────── */}
      <section style={{
        padding: "100px 80px 80px",
        borderBottom: `1px solid ${c.inkHair}`,
        textAlign: "center", position: "relative", overflow: "hidden",
      }}>
        {/* subtle grid texture */}
        <div style={{
          position: "absolute", inset: 0,
          backgroundImage: `linear-gradient(${c.inkHair} 1px, transparent 1px), linear-gradient(90deg, ${c.inkHair} 1px, transparent 1px)`,
          backgroundSize: "40px 40px", opacity: 0.5, pointerEvents: "none",
        }} />
        <div style={{ position: "relative", maxWidth: 960, margin: "0 auto" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 10,
            padding: "6px 14px",
            background: c.surface, border: `1px solid ${c.inkHairBold}`,
            fontFamily: fontMono, fontSize: 10, color: c.inkSoft,
            letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 36,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: c.vermillion }} />
            AI-NATIVE · 命令即工作
          </div>

          <h1 style={{
            fontFamily: fontHead, fontSize: 72, fontWeight: 500,
            color: c.ink, margin: 0, lineHeight: 1.1, letterSpacing: "0.03em",
          }}>
            一句話，<br />
            <span style={{ color: c.vermillion }}>萬事就位</span>。
          </h1>

          <p style={{
            fontFamily: fontHead, fontSize: 17, color: c.inkMuted,
            margin: "28px auto 0", maxWidth: 600, lineHeight: 1.8, letterSpacing: "0.04em",
          }}>
            ZenOS 是以 Agent 為核心、以自然語言為介面的知識工作台。<br />
            少點擊、少視窗、少分類。只需說，餘事自理。
          </p>

          {/* Prompt bar */}
          <div style={{
            margin: "60px auto 0", maxWidth: 720,
            background: c.surface, border: `1px solid ${c.inkHairBold}`,
            borderRadius: 2, padding: "18px 22px",
            display: "flex", alignItems: "center", gap: 14,
            boxShadow: `0 20px 50px -24px rgba(20,18,16,0.35)`,
            position: "relative",
          }}>
            <span style={{
              fontFamily: fontMono, fontSize: 13, color: c.vermillion,
              letterSpacing: "0.08em",
            }}>⌘ ›</span>
            <div style={{
              flex: 1, fontFamily: fontHead, fontSize: 17, color: c.ink,
              textAlign: "left", letterSpacing: "0.02em",
              overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis",
              height: 26,
            }}>
              <TypewriterPrompt text={prompts[promptIdx]} t={t} />
            </div>
            <span style={{
              fontFamily: fontMono, fontSize: 9, color: c.inkFaint,
              letterSpacing: "0.18em",
              padding: "4px 8px", border: `1px solid ${c.inkHair}`,
            }}>
              ⏎ 送出
            </span>
          </div>
          <div style={{
            fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
            letterSpacing: "0.22em", textTransform: "uppercase", marginTop: 18,
          }}>
            試試：任務 · 客戶 · 文件 · 會議 · 提醒
          </div>

          <div style={{ display: "flex", justifyContent: "center", gap: 14, marginTop: 56 }}>
            <button style={{
              padding: "14px 28px", background: c.ink, color: c.paper,
              border: "none", borderRadius: 2, cursor: "pointer",
              fontFamily: "inherit", fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase",
            }}>加入 Waitlist</button>
            <button style={{
              padding: "14px 24px", background: "transparent", color: c.ink,
              border: `1px solid ${c.inkHairBold}`, borderRadius: 2, cursor: "pointer",
              fontFamily: "inherit", fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase",
            }}>觀看演示</button>
          </div>
        </div>
      </section>

      {/* ── 信任帶 · numbers ─────────────────── */}
      <section style={{
        padding: "40px 80px", borderBottom: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
      }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto",
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0,
        }}>
          {[
            { k: "MODEL", v: "Claude · Haiku 4.5" },
            { k: "AVG LATENCY", v: "0.8s" },
            { k: "PRIVATE", v: "你的資料不訓模" },
            { k: "LOCAL-FIRST", v: "離線亦可用" },
          ].map((m, i) => (
            <div key={i} style={{
              padding: "0 24px", textAlign: "center",
              borderLeft: i > 0 ? `1px solid ${c.inkHair}` : "none",
            }}>
              <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.24em", marginBottom: 8 }}>{m.k}</div>
              <div style={{ fontFamily: fontHead, fontSize: 18, color: c.ink, letterSpacing: "0.04em" }}>{m.v}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 對話流 · Agent log as hero ─────────────── */}
      <section style={{ padding: "120px 80px", borderBottom: `1px solid ${c.inkHair}` }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 72 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 18 }}>
              一次對話的觀察
            </div>
            <h2 style={{ fontFamily: fontHead, fontSize: 44, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.04em", lineHeight: 1.25, maxWidth: 680, marginInline: "auto" }}>
              你說一句話，ZenOS 做六件事。
            </h2>
          </div>

          <div style={{
            maxWidth: 860, margin: "0 auto",
            background: c.surface, border: `1px solid ${c.inkHair}`,
            fontFamily: fontMono,
          }}>
            <div style={{
              padding: "12px 18px", borderBottom: `1px solid ${c.inkHair}`,
              display: "flex", justifyContent: "space-between",
              fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em",
            }}>
              <span>SESSION · 穀雨 / 週二 10:28</span>
              <span style={{ color: c.jade }}>● 串流中</span>
            </div>
            <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 14 }}>
              <LogLine t={t} kind="user" label="你" body="下週四要跟青山例會，替我準備好所有該看的東西。" />
              <LogLine t={t} kind="agent" label="ZenOS" body="收到。正為你梳理前置。" />
              <LogLine t={t} kind="tool" label="→ 搜尋" body="knowledge_graph.query(client=&quot;青山&quot;, range=14d) · 返回 42 筆" />
              <LogLine t={t} kind="tool" label="→ 歸類" body="會議紀要 5 · 決定 12 · 未竟事項 3 · 客戶回饋 2" />
              <LogLine t={t} kind="tool" label="→ 交叉" body="上週議程 vs 本週狀態 · 識別 2 項延續" />
              <LogLine t={t} kind="tool" label="→ 草擬" body="生成議程草稿 draft_0428.md · 附重點摘要" />
              <LogLine t={t} kind="tool" label="→ 建任務" body="提前 2h 預習 · 例會前 30min 覆盤 · 已排入節律" />
              <LogLine t={t} kind="agent" label="ZenOS" body="已備妥議程與兩份附件，放在 [青山 · 春分提案] 頁面。延續事項 2 項已標註。需要我先寄給你看？" />
              <LogLine t={t} kind="user" label="你" body="好。順便也幫我想三個開場問題。" />
              <LogLine t={t} kind="agent" label="ZenOS" body="——" blinking />
            </div>
          </div>
        </div>
      </section>

      {/* ── 命令表 · example prompts ────────── */}
      <section style={{ padding: "120px 80px", borderBottom: `1px solid ${c.inkHair}`, background: c.paperWarm }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 48 }}>
            <div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 14 }}>
                命令表 · PROMPT BOOK
              </div>
              <h2 style={{ fontFamily: fontHead, fontSize: 40, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.04em", lineHeight: 1.25 }}>
                能問什麼，就能做什麼。
              </h2>
            </div>
            <a style={{ fontFamily: fontMono, fontSize: 11, color: c.vermillion, letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer" }}>
              完整命令表 →
            </a>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {[
              { cat: "KNOWLEDGE", zh: "知識", ps: ["把過去三個月客戶反饋，分類為五個主題。", "哪些客戶 30 天內沒有聯絡過了？", "幫我找出所有談及『定價』的內部文件。"] },
              { cat: "MEETING",   zh: "會議", ps: ["下週四的例會，替我準備議程。", "整理昨日會議紀要給缺席的同事。", "這場會的決定有哪些還沒落地？"] },
              { cat: "CLIENT",    zh: "客戶", ps: ["替王總擬一封季度回訪信。", "青山的合約有哪些未完成項？", "過去一年對我貢獻最高的前五位客戶？"] },
              { cat: "RHYTHM",    zh: "節律", ps: ["本週我花最多時間在哪件事上？", "穀雨前要完成的任務還剩幾件？", "幫我為下週安排兩段深工時段。"] },
              { cat: "WRITE",     zh: "寫作", ps: ["把這份備忘錄精煉成三段摘要。", "替我把這封郵件譯成較禮貌的語氣。", "以春分提案為基礎，草擬一頁 one-pager。"] },
              { cat: "REMIND",    zh: "提醒", ps: ["下次見王總時，提醒我問合約第二期。", "穀雨當天，把春分提案 v2 交出去。", "週五之前若還沒收到回覆，自動催一次。"] },
            ].map((g, i) => (
              <div key={i} style={{
                padding: 24, background: c.surface, border: `1px solid ${c.inkHair}`,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 18, borderBottom: `1px solid ${c.inkHair}`, paddingBottom: 12 }}>
                  <div style={{ fontFamily: fontHead, fontSize: 16, color: c.ink, letterSpacing: "0.06em" }}>{g.zh}</div>
                  <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.24em" }}>{g.cat}</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {g.ps.map((p, j) => (
                    <div key={j} style={{
                      fontFamily: fontMono, fontSize: 11, color: c.inkSoft,
                      lineHeight: 1.7, letterSpacing: "0.02em",
                      padding: "8px 10px", background: c.paper,
                      borderLeft: `2px solid ${c.vermLine}`,
                    }}>
                      <span style={{ color: c.vermillion, marginRight: 6 }}>›</span>{p}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 三大支柱 · features compact ─────── */}
      <section style={{ padding: "120px 80px", borderBottom: `1px solid ${c.inkHair}` }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 72 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 14 }}>
              架構 · ARCHITECTURE
            </div>
            <h2 style={{ fontFamily: fontHead, fontSize: 40, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.04em" }}>
              三層結構，一以貫之。
            </h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0, borderTop: `1px solid ${c.inkHair}`, borderBottom: `1px solid ${c.inkHair}` }}>
            {[
              {
                code: "L1", zh: "記憶", en: "MEMORY",
                t: "一切匯流成地圖",
                d: "所有訊息、文件、對話、客戶，在背景連結成一張可查詢的知識地圖。",
                bullets: ["語意搜索 · 非關鍵字", "實體關聯 · 自動提取", "來源可追溯 · 每一句皆有出處"],
              },
              {
                code: "L2", zh: "動作", en: "ACTION",
                t: "能聽懂也能做到",
                d: "Agent 可讀、寫、分類、提醒、排程、草擬。你說的每一句命令，都能化為具體動作。",
                bullets: ["40+ 內建技能", "可插外部 MCP 工具", "人類批准機制"],
                highlight: true,
              },
              {
                code: "L3", zh: "節律", en: "RHYTHM",
                t: "讓紀律自動發生",
                d: "以你的時段與節氣為脈，ZenOS 為你安排專注、休整、盤點，讓紀律成為習慣。",
                bullets: ["個人節律學習", "團隊節律同步", "月度自動盤點"],
              },
            ].map((f, i) => (
              <div key={i} style={{
                padding: 36,
                borderLeft: i > 0 ? `1px solid ${c.inkHair}` : "none",
                background: f.highlight ? c.ink : "transparent",
                color: f.highlight ? c.paper : c.ink,
              }}>
                <div style={{ fontFamily: fontMono, fontSize: 10, opacity: 0.6, letterSpacing: "0.24em", marginBottom: 20 }}>
                  {f.code} · {f.en}
                </div>
                <div style={{ fontFamily: fontHead, fontSize: 36, color: f.highlight ? c.vermillion : c.vermillion, fontWeight: 500, letterSpacing: "0.06em", marginBottom: 14 }}>
                  {f.zh}
                </div>
                <h3 style={{ fontFamily: fontHead, fontSize: 20, fontWeight: 500, margin: "0 0 14px", letterSpacing: "0.04em" }}>
                  {f.t}
                </h3>
                <p style={{ fontSize: 13, lineHeight: 1.85, margin: "0 0 24px", opacity: 0.85, letterSpacing: "0.02em" }}>
                  {f.d}
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, borderTop: `1px solid ${f.highlight ? "rgba(244,239,228,0.15)" : c.inkHair}`, paddingTop: 16 }}>
                  {f.bullets.map((b, j) => (
                    <div key={j} style={{ fontFamily: fontMono, fontSize: 10, letterSpacing: "0.08em", opacity: 0.9, lineHeight: 1.7 }}>
                      · {b}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 整合 · integrations ─────────── */}
      <section style={{ padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`, background: c.paperWarm }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: 80, alignItems: "center" }}>
          <div>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 14 }}>
              整合 · INTEGRATIONS
            </div>
            <h2 style={{ fontFamily: fontHead, fontSize: 36, fontWeight: 500, color: c.ink, margin: "0 0 22px", letterSpacing: "0.04em", lineHeight: 1.3 }}>
              連得進來，<br />也放得出去。
            </h2>
            <p style={{ fontSize: 14, color: c.inkMuted, lineHeight: 1.85, margin: 0, letterSpacing: "0.02em" }}>
              ZenOS 支援 MCP 協議，可接入市面上絕大多數工作工具。你的資料隨你來、隨你去。不鎖、不困、不藏。
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            {[
              "Gmail","Slack","Notion","Drive",
              "Linear","GitHub","Figma","Zoom",
              "Calendar","LINE","Telegram","Dropbox",
            ].map((name, i) => (
              <div key={i} style={{
                padding: "18px 14px", background: c.surface,
                border: `1px solid ${c.inkHair}`, textAlign: "center",
                fontFamily: fontMono, fontSize: 11, color: c.inkSoft,
                letterSpacing: "0.12em",
              }}>{name}</div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Manifesto ─────────── */}
      <section style={{ padding: "100px 80px", borderBottom: `1px solid ${c.inkHair}`, background: c.ink, color: c.paper, textAlign: "center" }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: "rgba(244,239,228,0.5)", letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 28 }}>
            MANIFESTO · 信念書
          </div>
          <h2 style={{ fontFamily: fontHead, fontSize: 28, fontWeight: 400, color: c.paper, margin: 0, letterSpacing: "0.06em", lineHeight: 1.95 }}>
            最強大的介面，是沒有介面。<br />
            最好的工具，是你幾乎感覺不到它。<br />
            ZenOS 把 AI 藏在背景，讓意圖走到前臺。<br />
            <span style={{ color: c.vermillion }}>一句話，萬事就位。</span>
          </h2>
        </div>
      </section>

      {/* ── Final CTA ─────────── */}
      <section style={{ padding: "110px 80px", textAlign: "center", borderBottom: `1px solid ${c.inkHair}` }}>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 20 }}>ENTER · 入場</div>
        <h2 style={{ fontFamily: fontHead, fontSize: 56, fontWeight: 500, color: c.ink, margin: "0 0 28px", letterSpacing: "0.05em" }}>
          準備好下第一道命令？
        </h2>
        <p style={{ fontFamily: fontHead, fontSize: 15, color: c.inkMuted, maxWidth: 500, margin: "0 auto 44px", lineHeight: 1.85, letterSpacing: "0.03em" }}>
          內測名額有限。留下一封信，我們會在下一批邀請中帶上你。
        </p>
        <div style={{
          display: "flex", gap: 0, maxWidth: 500, margin: "0 auto",
          border: `1px solid ${c.inkHairBold}`, borderRadius: 2, background: c.surface,
          fontFamily: fontMono,
        }}>
          <span style={{ padding: "14px 0 14px 18px", color: c.vermillion, fontSize: 14 }}>⌘ ›</span>
          <input placeholder="name@company.tw" style={{
            flex: 1, padding: "14px 14px", background: "transparent",
            border: "none", outline: "none",
            fontFamily: fontMono, fontSize: 13, color: c.ink, letterSpacing: "0.04em",
          }} />
          <button style={{
            padding: "0 28px", background: c.ink, color: c.paper,
            border: "none", cursor: "pointer",
            fontFamily: "inherit", fontSize: 11, letterSpacing: "0.2em", textTransform: "uppercase",
          }}>發送 ⏎</button>
        </div>
      </section>

      <LandingFooter t={t} />
    </div>
  );
}

// — helpers —
function TypewriterPrompt({ text, t }) {
  const [shown, setShown] = React.useState("");
  React.useEffect(() => {
    setShown("");
    let i = 0;
    const id = setInterval(() => {
      i++;
      setShown(text.slice(0, i));
      if (i >= text.length) clearInterval(id);
    }, 28);
    return () => clearInterval(id);
  }, [text]);
  return (
    <>
      {shown}
      <span style={{ borderRight: `2px solid ${t.c.vermillion}`, marginLeft: 2, animation: "zen-blink 1s steps(2) infinite", height: 18, display: "inline-block", verticalAlign: "middle" }} />
    </>
  );
}

function LogLine({ t, kind, label, body, blinking }) {
  const { c, fontMono, fontHead } = t;
  const color =
    kind === "user"  ? c.ink :
    kind === "agent" ? c.vermillion :
                       c.inkFaint;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "90px 1fr", gap: 18, alignItems: "baseline" }}>
      <div style={{
        fontFamily: fontMono, fontSize: 10, color, letterSpacing: "0.2em",
        textTransform: "uppercase", textAlign: "right",
      }}>{label}</div>
      <div style={{
        fontFamily: kind === "tool" ? fontMono : fontHead,
        fontSize: kind === "tool" ? 11 : 14,
        color: kind === "tool" ? c.inkSoft : c.ink,
        lineHeight: 1.7, letterSpacing: "0.03em",
      }}>
        {body}
        {blinking && <span style={{ borderRight: `2px solid ${c.vermillion}`, marginLeft: 4, animation: "zen-blink 1s steps(2) infinite", display: "inline-block", height: 16, verticalAlign: "middle" }} />}
      </div>
    </div>
  );
}

window.LandingC = LandingC;
