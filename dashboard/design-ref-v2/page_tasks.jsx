// ZenOS v2 · Today + Tasks page (Zen Ink)
const { useState: useS, useMemo: useM } = React;

function HeroToday({ t }) {
  const { c, fontHead, fontMono, fontBody, solarTerm } = t;
  return (
    <div style={{
      position: "relative",
      padding: "48px 48px 44px",
      borderBottom: `1px solid ${c.inkHair}`,
      background: c.paper,
      overflow: "hidden",
    }}>
      {/* Watermark 節氣 */}
      <div style={{
        position: "absolute", right: 36, top: 20, bottom: 20,
        display: "flex", alignItems: "center", pointerEvents: "none",
        fontFamily: fontHead, fontSize: 220, fontWeight: 500,
        color: c.ink, opacity: 0.04, letterSpacing: "0.1em",
        writingMode: "vertical-rl",
      }}>
        {solarTerm.name}
      </div>
      <div style={{ position: "relative", display: "flex", alignItems: "flex-start", gap: 28 }}>
        <SealChop text={solarTerm.name} seal={c.seal} size={60} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
            2026 · 04 · 19 · SATURDAY
          </div>
          <h1 style={{ fontFamily: fontHead, fontSize: 44, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.04em", lineHeight: 1.1 }}>
            今日工作台
          </h1>
          <p style={{ fontFamily: fontBody, fontSize: 14, color: c.inkMuted, margin: "12px 0 0", fontWeight: 400, letterSpacing: "0.02em" }}>
            今日有 3 項 P0 任務待處理，2 場會議，預計專注時段 3.5 小時。
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
            <Chip t={t} tone="accent" dot>2 · P0 待處理</Chip>
            <Chip t={t} tone="ocher" dot>3 · 進行中</Chip>
            <Chip t={t} tone="jade" dot>4 · 本週完成</Chip>
            <Chip t={t} tone="muted">專注時數 · 3.5h</Chip>
          </div>
        </div>
      </div>
    </div>
  );
}

const TASKS = [
  { id: 1,  title: "重構 Knowledge Graph 向量索引",     s: "todo",    p: "critical", who: "怡君", due: "04/22", tags: ["infra", "pgvector"] },
  { id: 2,  title: "客戶 Acme 的產品演示 follow-up",    s: "todo",    p: "critical", who: "品瑄", due: "今日",  tags: ["customer"] },
  { id: 3,  title: "草擬 Q2 OKR 初版",                 s: "todo",    p: "medium",   who: "Me",   due: "04/25", tags: ["planning"] },
  { id: 4,  title: "行銷部落格：節氣式工作法",          s: "todo",    p: "low",      who: "子豪", due: "05/01", tags: ["blog"] },
  { id: 5,  title: "重寫拖拉動效（降低延遲）",          s: "active",  p: "high",     who: "Me",   due: "04/21", tags: ["frontend"] },
  { id: 6,  title: "修：分頁在行動裝置斷版",            s: "active",  p: "medium",   who: "怡君", due: "04/20", tags: ["bug"] },
  { id: 7,  title: "串接 OpenAI Structured Output",    s: "active",  p: "high",     who: "宗翰", due: "04/23", tags: ["llm"] },
  { id: 8,  title: "權限治理：邊界案例補測",            s: "review",  p: "critical", who: "品瑄", due: "04/19", tags: ["governance"] },
  { id: 9,  title: "CRM 自動 enrich 邏輯",             s: "review",  p: "medium",   who: "宗翰", due: "04/20", tags: ["agent"] },
  { id: 10, title: "把 Morning Report 改成可訂閱",      s: "done",    p: "low",      who: "Me",   due: "04/15", tags: ["feature"] },
  { id: 11, title: "Playwright e2e：Deal 建立",         s: "done",    p: "medium",   who: "怡君", due: "04/16", tags: ["qa"] },
];
const COLS = [
  { k: "todo",   zh: "待處理", en: "Idle" },
  { k: "active", zh: "進行中", en: "Flow" },
  { k: "review", zh: "審查中", en: "Review" },
  { k: "done",   zh: "已完成", en: "Done" },
];

function InkCard({ t, task, onOpen }) {
  const { c, fontHead, fontBody, fontMono } = t;
  const [hv, setHv] = useS(false);
  const pri = {
    critical: { fg: c.seal,   mark: "一" },
    high:     { fg: c.ocher,  mark: "二" },
    medium:   { fg: c.inkMuted, mark: "三" },
    low:      { fg: c.inkFaint, mark: "四" },
  }[task.p];
  return (
    <div onClick={() => onOpen && onOpen(task)} onMouseEnter={() => setHv(true)} onMouseLeave={() => setHv(false)}
      style={{
        background: hv ? c.surfaceHi : c.surface,
        border: `1px solid ${hv ? c.inkHairBold : c.inkHair}`,
        borderRadius: 2,
        padding: "14px 16px 12px",
        cursor: "pointer",
        transition: "all .14s",
        position: "relative",
      }}>
      {/* vertical priority mark */}
      <div style={{
        position: "absolute", left: -1, top: 14, bottom: 14, width: 2,
        background: pri.fg, opacity: 0.85,
      }} />
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8 }}>
        <span style={{
          fontFamily: fontHead, fontSize: 14, color: pri.fg,
          letterSpacing: "0.08em", fontWeight: 500,
        }}>{pri.mark}</span>
        <div style={{
          fontSize: 13.5, color: c.ink, lineHeight: 1.5,
          fontFamily: fontBody, fontWeight: 400, flex: 1,
        }}>{task.title}</div>
      </div>
      <div style={{ display: "flex", gap: 7, marginBottom: 10, flexWrap: "wrap" }}>
        {task.tags.map(tg => (
          <span key={tg} style={{
            fontFamily: fontMono, fontSize: 10,
            color: c.inkFaint, letterSpacing: "0.04em",
          }}>·{tg}</span>
        ))}
      </div>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        paddingTop: 10, borderTop: `1px solid ${c.inkHair}`,
        fontSize: 11, color: c.inkMuted,
      }}>
        <div style={{
          width: 20, height: 20, borderRadius: 2,
          background: c.vermSoft, color: c.vermillion,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, fontFamily: fontHead, fontWeight: 600,
          border: `1px solid ${c.vermLine}`,
        }}>{task.who[0]}</div>
        <span style={{ letterSpacing: "0.04em" }}>{task.who}</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontFamily: fontMono, fontSize: 10, color: task.due === "今日" ? c.vermillion : c.inkFaint }}>
          {task.due}
        </span>
      </div>
    </div>
  );
}

function TasksPage({ t }) {
  const { c, fontHead, fontMono } = t;
  const [tab, setTab] = useS("all");
  const [open, setOpen] = useS(null);
  const tabs = [
    { k: "all",  zh: "全部",     en: "All",      n: TASKS.length },
    { k: "me",   zh: "我的",     en: "Mine",     n: TASKS.filter(x => x.who === "Me").length },
    { k: "due",  zh: "即將到期", en: "Due soon", n: 4 },
    { k: "risk", zh: "風險",     en: "At risk",  n: 2 },
  ];
  const grouped = useM(() => {
    const g = {};
    COLS.forEach(col => g[col.k] = TASKS.filter(x => x.s === col.k));
    return g;
  }, []);
  return (
    <>
      <HeroToday t={t} />
      <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
        <Section t={t}
          eyebrow="WORK · 任務"
          title="任務"
          en="Tasks"
          subtitle="本週所有進行中的任務，依狀態分為四欄。"
          right={
            <div style={{ display: "flex", gap: 10 }}>
              <Btn t={t} variant="ghost" icon={Icons.filter}>篩選</Btn>
              <Btn t={t} variant="outline" icon={Icons.spark}>Agent 分派</Btn>
              <Btn t={t} variant="seal" icon={Icons.plus}>新任務</Btn>
            </div>
          }
        />

        {/* Tabs — East-style underline */}
        <div style={{ display: "flex", gap: 28, borderBottom: `1px solid ${c.inkHair}`, marginBottom: 28 }}>
          {tabs.map(tb => {
            const active = tab === tb.k;
            return (
              <button key={tb.k} onClick={() => setTab(tb.k)} style={{
                padding: "12px 2px",
                background: "transparent", border: "none",
                borderBottom: active ? `2px solid ${c.ink}` : "2px solid transparent",
                color: active ? c.ink : c.inkMuted,
                cursor: "pointer", fontFamily: t.fontBody,
                fontSize: 13, fontWeight: active ? 500 : 400,
                marginBottom: -1,
                display: "flex", alignItems: "baseline", gap: 8,
                letterSpacing: "0.05em",
              }}>
                <span>{tb.zh}</span>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: active ? c.vermillion : c.inkFaint }}>
                  {String(tb.n).padStart(2, "0")}
                </span>
              </button>
            );
          })}
        </div>

        {/* Board */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 24 }}>
          {COLS.map(col => (
            <div key={col.k} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{
                display: "flex", alignItems: "baseline", justifyContent: "space-between",
                paddingBottom: 12, borderBottom: `1px solid ${c.inkHair}`,
              }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                  <span style={{
                    fontFamily: fontHead, fontSize: 15, color: c.ink,
                    fontWeight: 500, letterSpacing: "0.08em",
                  }}>{col.zh}</span>
                  <span style={{
                    fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
                    letterSpacing: "0.15em", textTransform: "uppercase",
                  }}>{col.en}</span>
                </div>
                <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted }}>
                  {String(grouped[col.k].length).padStart(2, "0")}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {grouped[col.k].map(x => <InkCard key={x.id} task={x} t={t} onOpen={setOpen} />)}
                <button style={{
                  padding: "10px",
                  background: "transparent", border: `1px dashed ${c.inkHair}`,
                  borderRadius: 2, color: c.inkFaint, fontSize: 11,
                  cursor: "pointer", fontFamily: t.fontBody, letterSpacing: "0.05em",
                }}>＋ 新增</button>
              </div>
            </div>
          ))}
        </div>
      </div>
      {open && <TaskDrawer t={t} task={open} onClose={() => setOpen(null)} />}
    </>
  );
}

// ─── Task Drawer (second layer) ────────────────────────────────────────
function TaskDrawer({ t, task, onClose }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const pri = {
    critical: { zh: "P0 · 極高", mark: "一", tone: "accent" },
    high:     { zh: "P1 · 高",   mark: "二", tone: "ocher"  },
    medium:   { zh: "P2 · 中",   mark: "三", tone: "muted"  },
    low:      { zh: "P3 · 低",   mark: "四", tone: "muted"  },
  }[task.p];
  const statusMap = { todo: "待處理", active: "進行中", review: "審查中", done: "已完成" };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 80,
      background: "rgba(20,18,16,0.35)", backdropFilter: "blur(4px)",
      display: "flex", justifyContent: "flex-end",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 540, height: "100%", background: c.paper,
        borderLeft: `1px solid ${c.inkHairBold}`,
        overflowY: "auto", boxShadow: "-20px 0 60px rgba(20,18,16,0.2)",
        animation: "slidein .18s ease-out",
      }}>
        <style>{`@keyframes slidein { from { transform: translateX(20px); opacity: 0.6; } to { transform: translateX(0); opacity: 1; } }`}</style>

        {/* Header */}
        <div style={{
          padding: "20px 28px 18px",
          borderBottom: `1px solid ${c.inkHair}`,
          background: c.surface,
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
                TASK · #{String(task.id).padStart(3, "0")}
              </span>
              <Chip t={t} tone={pri.tone} dot>{pri.zh}</Chip>
              <Chip t={t} tone={task.s === "done" ? "jade" : task.s === "review" ? "ocher" : "muted"}>{statusMap[task.s]}</Chip>
            </div>
            <button onClick={onClose} style={{
              background: "transparent", border: "none", color: c.inkMuted,
              cursor: "pointer", padding: 4, fontFamily: fontMono, fontSize: 16,
            }}>✕</button>
          </div>
          <h2 style={{ fontFamily: fontHead, fontSize: 22, fontWeight: 500, color: c.ink, margin: 0, lineHeight: 1.35, letterSpacing: "0.02em" }}>
            {task.title}
          </h2>
          <div style={{ display: "flex", gap: 18, marginTop: 14, fontSize: 12.5, color: c.inkMuted }}>
            <span>負責 · <span style={{ color: c.ink }}>{task.who}</span></span>
            <span>到期 · <span style={{ color: task.due === "今日" ? c.vermillion : c.ink, fontFamily: fontMono }}>{task.due}</span></span>
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
            {task.tags.map(tg => <Chip key={tg} t={t} tone="muted">#{tg}</Chip>)}
          </div>
        </div>

        {/* Agent suggestion */}
        <div style={{ padding: "20px 28px", borderBottom: `1px solid ${c.inkHair}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Icon d={Icons.spark} size={12} style={{ color: c.vermillion }} />
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
              Agent 建議
            </span>
          </div>
          <div style={{
            padding: "12px 14px", background: c.vermSoft,
            border: `1px solid ${c.vermLine}`, borderRadius: 2,
            fontSize: 12.5, color: c.ink, lineHeight: 1.7,
          }}>
            依過去相似任務，建議先完成「資料結構調研」，再進入「index rebuild」。估計 3-4 小時。
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <Btn t={t} variant="ghost" size="sm">採用建議</Btn>
            <Btn t={t} variant="ghost" size="sm">拆成子任務</Btn>
          </div>
        </div>

        {/* Subtasks */}
        <div style={{ padding: "20px 28px", borderBottom: `1px solid ${c.inkHair}` }}>
          <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, letterSpacing: "0.04em", marginBottom: 10 }}>
            子任務
          </div>
          {[
            { d: true,  t: "調研 pgvector 0.7 新語法" },
            { d: true,  t: "比較 hybrid search 策略" },
            { d: false, t: "重寫 index rebuild 流程" },
            { d: false, t: "回歸測試 + 效能比對" },
          ].map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none" }}>
              <span style={{
                width: 14, height: 14, borderRadius: 2,
                border: `1px solid ${s.d ? c.ink : c.inkHair}`,
                background: s.d ? c.ink : "transparent",
                color: c.paper, display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: fontMono, fontSize: 8,
              }}>{s.d ? "✓" : ""}</span>
              <span style={{
                fontSize: 12.5, color: s.d ? c.inkMuted : c.ink,
                textDecoration: s.d ? "line-through" : "none",
                textDecorationColor: c.inkFaint, flex: 1,
              }}>{s.t}</span>
            </div>
          ))}
          <button style={{
            marginTop: 10, padding: "6px 10px",
            background: "transparent", border: `1px dashed ${c.inkHair}`,
            borderRadius: 2, color: c.inkFaint, fontSize: 11,
            cursor: "pointer", fontFamily: fontBody, letterSpacing: "0.04em",
          }}>＋ 新增子任務</button>
        </div>

        {/* Activity */}
        <div style={{ padding: "20px 28px 40px" }}>
          <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, fontWeight: 500, letterSpacing: "0.04em", marginBottom: 10 }}>
            動態
          </div>
          {[
            { t: "04/18 15:10", who: task.who, zh: "更新狀態為「進行中」。" },
            { t: "04/17 11:20", who: "Agent", zh: "從 Demo 複盤建立此任務。" },
          ].map((a, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "110px 1fr",
              gap: 14, padding: "10px 0",
              borderBottom: i < 1 ? `1px solid ${c.inkHair}` : "none",
            }}>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>{a.t}</span>
              <div>
                <div style={{ fontSize: 12.5, color: c.ink, lineHeight: 1.5 }}>
                  <span style={{ fontWeight: 500 }}>{a.who}</span> · {a.zh}
                </div>
              </div>
            </div>
          ))}
          <div style={{
            marginTop: 16, display: "flex", gap: 8,
            padding: "8px 12px", background: c.surface,
            border: `1px solid ${c.inkHair}`, borderRadius: 2,
          }}>
            <input placeholder="留下一則註記…" style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              fontFamily: fontBody, fontSize: 12.5, color: c.ink,
            }} />
            <Btn t={t} variant="ink" size="sm">送出</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

window.InkTasksPage = TasksPage;
