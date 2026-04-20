// ZenOS v2 · Zen Ink components (B-only, deepened)
const { useState, useEffect, useRef, useMemo } = React;

// ─── Brand mark · enso with seal ──────────────────────────────────────
const InkMark = ({ size = 32, ink, seal, style }) => (
  <svg width={size} height={size} viewBox="0 0 44 44" style={style}>
    <defs>
      <filter id="inkRough" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence baseFrequency="0.9" numOctaves="2" seed="3" />
        <feDisplacementMap in="SourceGraphic" scale="0.6" />
      </filter>
    </defs>
    <path d="M 22 6 A 16 16 0 1 1 10 35" fill="none" stroke={ink} strokeWidth="2.6"
          strokeLinecap="round" filter="url(#inkRough)" opacity="0.92" />
    <rect x="29" y="27" width="9" height="9" rx="1" fill={seal} opacity="0.9" />
    <text x="33.5" y="34" textAnchor="middle" fill="#FFF2EC" fontSize="6.5" fontFamily="serif" fontWeight="700">禪</text>
  </svg>
);

// ─── Icon glyphs — calligraphic weight ────────────────────────────────
const Icon = ({ d, size = 16, stroke = 1.4, style = {} }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
       style={{ flexShrink: 0, ...style }}>
    {typeof d === "string" ? <path d={d} /> : d}
  </svg>
);
const Icons = {
  search:  "M11 19a8 8 0 100-16 8 8 0 000 16zm10 2l-4.35-4.35",
  plus:    "M12 5v14M5 12h14",
  chev:    "M9 6l6 6-6 6",
  zen:     <><circle cx="12" cy="12" r="9" /><path d="M3 12a9 9 0 0118 0" /></>,
  task:    "M4 6h16M4 12h16M4 18h10",
  folder:  "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z",
  users:   "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8z",
  map:     "M9 3L2 6v15l7-3 6 3 7-3V3l-7 3-6-3zM9 3v15M15 6v15",
  trend:   "M3 17l6-6 4 4 8-8M14 7h7v7",
  doc:     "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6",
  spark:   "M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z",
  arrow:   "M5 12h14M13 6l6 6-6 6",
  filter:  "M3 6h18M6 12h12M10 18h4",
  settings:"M12 15a3 3 0 100-6 3 3 0 000 6zm7.4-3a7.4 7.4 0 00-.1-1.4l2-1.6-2-3.4-2.4.8a7.4 7.4 0 00-2.4-1.4L14 2h-4l-.5 2.6a7.4 7.4 0 00-2.4 1.4l-2.4-.8-2 3.4 2 1.6a7.4 7.4 0 000 2.8l-2 1.6 2 3.4 2.4-.8a7.4 7.4 0 002.4 1.4L10 22h4l.5-2.6a7.4 7.4 0 002.4-1.4l2.4.8 2-3.4-2-1.6z",
  moon:    "M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z",
  sun:     "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 7a5 5 0 110 10 5 5 0 010-10z",
  clock:   <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  link:    "M10 14a5 5 0 017 0l3-3a5 5 0 10-7-7l-1 1m-2 8a5 5 0 01-7 0l-3 3a5 5 0 107 7l1-1",
  check:   "M5 13l4 4L19 7",
};

// ─── Seal chop — vertical 篆書 mark, used as watermark / brand stamp ──
const SealChop = ({ text = "禪作", seal, size = 44 }) => (
  <div style={{
    display: "inline-flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    width: size, height: size,
    background: seal, color: "#FFF2EC",
    fontFamily: '"Noto Serif TC", "Songti TC", serif', fontWeight: 700,
    fontSize: size * 0.32, lineHeight: 1, letterSpacing: "0.05em",
    borderRadius: 2,
    boxShadow: "inset 0 0 0 1px rgba(255,242,236,0.12), inset 0 0 0 3px " + seal,
  }}>
    {text.split("").map((ch, i) => <span key={i} style={{ padding: "1px 0" }}>{ch}</span>)}
  </div>
);

// ─── Primitive: hairline divider (subtle brush texture via gradient) ──
const Divider = ({ ink, style, vertical }) => (
  <div style={{
    [vertical ? "width" : "height"]: 1,
    [vertical ? "height" : "width"]: "100%",
    background: `linear-gradient(${vertical ? "180deg" : "90deg"}, transparent 0%, ${ink} 15%, ${ink} 85%, transparent 100%)`,
    opacity: 0.6,
    ...style,
  }} />
);

// ─── Chip ─────────────────────────────────────────────────────────────
function Chip({ children, t, tone = "muted", dot, style }) {
  const { c, fontBody } = t;
  const tones = {
    muted:   { fg: c.inkMuted, bd: c.inkHair },
    accent:  { fg: c.vermillion, bd: c.vermLine },
    jade:    { fg: c.jade,      bd: c.inkHair },
    ocher:   { fg: c.ocher,     bd: c.inkHair },
    plain:   { fg: c.inkMuted,  bd: "transparent" },
  };
  const tn = tones[tone] || tones.muted;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px",
      color: tn.fg,
      border: `1px solid ${tn.bd}`, borderRadius: 2,
      fontSize: 11, lineHeight: "16px",
      fontFamily: fontBody, fontWeight: 400,
      letterSpacing: "0.02em",
      ...style,
    }}>
      {dot && <span style={{ width: 5, height: 5, borderRadius: "50%", background: tn.fg }} />}
      {children}
    </span>
  );
}

// ─── Button ────────────────────────────────────────────────────────────
function Btn({ children, t, variant = "ghost", icon, onClick, size = "md", style }) {
  const { c, fontBody, radius } = t;
  const [hv, setHv] = useState(false);
  const s = { sm: { p: "4px 10px", fs: 11, ic: 12 }, md: { p: "7px 14px", fs: 12, ic: 13 }, lg: { p: "10px 20px", fs: 13, ic: 14 } }[size];
  const V = {
    ink: { bg: hv ? c.inkSoft : c.ink, fg: c.paper, bd: "transparent" },
    outline: { bg: hv ? c.surfaceHi : "transparent", fg: c.ink, bd: c.inkHairBold },
    ghost: { bg: hv ? c.surface : "transparent", fg: hv ? c.ink : c.inkMuted, bd: c.inkHair },
    seal: { bg: hv ? c.seal : c.vermillion, fg: "#FFF2EC", bd: "transparent" },
  }[variant];
  return (
    <button onClick={onClick} onMouseEnter={() => setHv(true)} onMouseLeave={() => setHv(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 7,
        padding: s.p, fontSize: s.fs, fontFamily: fontBody,
        fontWeight: 500, letterSpacing: "0.02em",
        background: V.bg, color: V.fg,
        border: `1px solid ${V.bd}`, borderRadius: radius,
        cursor: "pointer", transition: "all .15s",
        ...style,
      }}>
      {icon && <Icon d={icon} size={s.ic} />}
      {children}
    </button>
  );
}

// ─── Section title with east-style vertical mark ──────────────────────
function Section({ num, eyebrow, title, en, subtitle, right, t }) {
  const { c, fontHead, fontMono } = t;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 24, marginBottom: 28 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
        {num && (
          <div style={{
            writingMode: "vertical-rl", textOrientation: "mixed",
            fontFamily: fontHead, fontSize: 11, color: c.inkFaint,
            letterSpacing: "0.2em", paddingTop: 4,
            borderRight: `1px solid ${c.inkHair}`, paddingRight: 10, marginRight: 4,
          }}>
            {num}
          </div>
        )}
        <div>
          {eyebrow && (
            <div style={{
              fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
              letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8,
            }}>{eyebrow}</div>
          )}
          <h2 style={{
            fontFamily: fontHead, fontSize: 34, fontWeight: 500,
            color: c.ink, margin: 0, letterSpacing: "0.02em",
            lineHeight: 1.1,
          }}>
            {title}
            {en && <span style={{
              marginLeft: 14, fontFamily: '"Helvetica Neue", Helvetica, serif',
              fontWeight: 300, fontSize: 22, color: c.inkFaint,
              letterSpacing: "-0.01em", fontStyle: "italic",
            }}>{en}</span>}
          </h2>
          {subtitle && (
            <p style={{
              fontSize: 13, color: c.inkMuted, margin: "10px 0 0",
              maxWidth: 620, lineHeight: 1.65, fontWeight: 300,
            }}>{subtitle}</p>
          )}
        </div>
      </div>
      {right && <div style={{ paddingBottom: 6 }}>{right}</div>}
    </div>
  );
}

// ─── Shell · vertical nav with seal chop and 節氣 footer ──────────────
function Shell({ t, activeNav, onNavChange, onOpenCmdK, onToggleMode, children }) {
  const { c, fontHead, fontBody, fontMono, solarTerm, mode } = t;
  const nav = [
    { k: "map",       zh: "知識地圖", en: "Knowledge",   icon: Icons.map },
    { k: "home",      zh: "今日",     en: "Today",       icon: Icons.zen },
    { k: "tasks",     zh: "任務",     en: "Tasks",       icon: Icons.task },
    { k: "projects",  zh: "專案",     en: "Projects",    icon: Icons.folder },
    { k: "clients",   zh: "客戶",     en: "Clients",     icon: Icons.users },
    { k: "marketing", zh: "行銷",     en: "Growth",      icon: Icons.trend },
    { k: "docs",      zh: "文件",     en: "Docs",        icon: Icons.doc },
  ];

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "240px 1fr",
      height: "100vh", background: c.paper, color: c.ink,
      fontFamily: fontBody, letterSpacing: "0.005em",
    }}>
      <aside style={{
        borderRight: `1px solid ${c.inkHair}`,
        padding: "24px 18px 18px",
        display: "flex", flexDirection: "column",
        background: c.paperWarm,
      }}>
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 22 }}>
          <InkMark size={30} ink={c.ink} seal={c.seal} />
          <div>
            <div style={{ fontFamily: fontHead, fontSize: 18, fontWeight: 500, letterSpacing: "0.05em", color: c.ink }}>
              ZenOS
            </div>
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.18em", marginTop: 1 }}>
              v2 · WORKSPACE
            </div>
          </div>
        </div>

        {/* ⌘K */}
        <button onClick={onOpenCmdK} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "9px 12px", marginBottom: 22,
          background: c.surface, border: `1px solid ${c.inkHair}`,
          borderRadius: 2, color: c.inkMuted,
          fontSize: 12, fontFamily: fontBody,
          cursor: "pointer", width: "100%", transition: "all .15s",
        }}
          onMouseEnter={e => e.currentTarget.style.borderColor = c.inkHairBold}
          onMouseLeave={e => e.currentTarget.style.borderColor = c.inkHair}>
          <Icon d={Icons.search} size={13} />
          <span style={{ flex: 1, textAlign: "left", letterSpacing: "0.01em" }}>搜尋 · 指令</span>
          <kbd style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>⌘K</kbd>
        </button>

        {/* Nav label */}
        <div style={{
          fontFamily: fontMono, fontSize: 9,
          color: c.inkFaint, letterSpacing: "0.2em",
          textTransform: "uppercase", padding: "0 4px 10px",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span>Navigation</span>
          <div style={{ flex: 1, height: 1, background: c.inkHair }} />
        </div>

        {nav.map(it => {
          const active = activeNav === it.k;
          return (
            <button key={it.k} onClick={() => onNavChange?.(it.k)}
              style={{
                display: "grid", gridTemplateColumns: "18px 1fr auto",
                alignItems: "center", gap: 12,
                padding: "9px 10px",
                background: active ? c.surface : "transparent",
                border: "none",
                borderLeft: active ? `2px solid ${c.vermillion}` : "2px solid transparent",
                color: active ? c.ink : c.inkMuted,
                cursor: "pointer", textAlign: "left",
                fontFamily: fontBody,
                transition: "all .15s",
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.color = c.ink; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.color = c.inkMuted; }}>
              <Icon d={it.icon} size={14} stroke={active ? 1.8 : 1.4} />
              <span style={{ fontSize: 13, fontWeight: active ? 500 : 400, letterSpacing: "0.04em" }}>
                {it.zh}
              </span>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>
                {it.en}
              </span>
            </button>
          );
        })}

        <div style={{ flex: 1 }} />

        {/* Footer · account + mode */}
        <div style={{
          padding: "14px 4px 4px", borderTop: `1px solid ${c.inkHair}`,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: "50%",
            background: c.vermSoft, border: `1px solid ${c.vermLine}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: fontHead, fontSize: 12, color: c.vermillion, fontWeight: 600,
          }}>B</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: fontBody, fontSize: 12.5, color: c.ink, fontWeight: 500, letterSpacing: "0.02em" }}>
              Barry
            </div>
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 1 }}>
              Workspace
            </div>
          </div>
          <button onClick={onToggleMode} style={{
            background: "transparent", border: `1px solid ${c.inkHair}`,
            borderRadius: 2, padding: 6, color: c.inkMuted, cursor: "pointer",
          }}>
            <Icon d={mode === "dark" ? Icons.sun : Icons.moon} size={14} />
          </button>
        </div>
      </aside>

      <main style={{ overflow: "auto", position: "relative" }}>
        {children}
      </main>
    </div>
  );
}

// ─── Cmd K ─────────────────────────────────────────────────────────────
function CmdK({ t, open, onClose }) {
  const { c, fontHead, fontBody, fontMono } = t;
  const [q, setQ] = useState("");
  const inpRef = useRef(null);
  useEffect(() => { if (open) setTimeout(() => inpRef.current?.focus(), 20); }, [open]);
  if (!open) return null;
  const groups = [
    { g: "Agent Actions", items: [
      { l: "產生本週回顧摘要",       h: "Summary" },
      { l: "列出所有阻塞的 P0 任務", h: "Triage" },
      { l: "草擬給 Acme 的後續信件", h: "CRM" },
    ]},
    { g: "跳轉", items: [
      { l: "知識地圖",   h: "G M" },
      { l: "任務看板",   h: "G T" },
      { l: "客戶",       h: "G C" },
    ]},
  ];
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 100,
      background: "rgba(20,18,16,0.42)",
      backdropFilter: "blur(10px)",
      display: "flex", alignItems: "flex-start", justifyContent: "center",
      paddingTop: "13vh",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 640, maxWidth: "92%",
        background: c.surfaceHi,
        border: `1px solid ${c.inkHairBold}`,
        borderRadius: 2, overflow: "hidden",
        boxShadow: "0 40px 80px rgba(20,18,16,0.25)",
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "16px 20px",
          borderBottom: `1px solid ${c.inkHair}`,
        }}>
          <Icon d={Icons.search} size={16} style={{ color: c.inkMuted }} />
          <input ref={inpRef} value={q} onChange={e => setQ(e.target.value)}
            placeholder="搜尋或輸入指令…"
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: c.ink, fontSize: 16, fontFamily: fontHead,
              fontWeight: 400, letterSpacing: "0.02em",
            }} />
          <kbd style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>ESC</kbd>
        </div>
        <div style={{ maxHeight: 440, overflow: "auto" }}>
          {groups.map((g, gi) => (
            <div key={gi}>
              <div style={{
                padding: "12px 20px 6px",
                fontFamily: fontMono, fontSize: 9,
                color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase",
              }}>{g.g}</div>
              {g.items.map((it, ii) => (
                <button key={ii} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  width: "100%", padding: "10px 20px",
                  background: "transparent", border: "none",
                  color: c.ink, cursor: "pointer", fontSize: 13,
                  textAlign: "left", fontFamily: fontBody,
                }}
                  onMouseEnter={e => e.currentTarget.style.background = c.surface}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <Icon d={Icons.spark} size={13} style={{ color: c.vermillion }} />
                  <span style={{ flex: 1 }}>{it.l}</span>
                  <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>{it.h}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { InkMark, Icon, Icons, SealChop, Divider, Chip, Btn, Section, Shell, CmdK });
