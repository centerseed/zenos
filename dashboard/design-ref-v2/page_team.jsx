// ZenOS v2 · Team (團隊)
const { useState: useTeamS } = React;

const MEMBERS = [
  { id: "m1", n: "林品瑄", handle: "@pinxuan",    role: "Owner",    title: "共同創辦人",      status: "online",  joined: "2025-08",  lastActive: "現在",          agents: 4, tasks: 18 },
  { id: "m2", n: "陳怡君", handle: "@yichun",     role: "Admin",    title: "工程主管",       status: "online",  joined: "2025-09",  lastActive: "5 分鐘前",      agents: 3, tasks: 12 },
  { id: "m3", n: "宗翰",   handle: "@zonghan",    role: "Member",   title: "資深工程師",      status: "online",  joined: "2025-10",  lastActive: "22 分鐘前",     agents: 2, tasks: 15 },
  { id: "m4", n: "子豪",   handle: "@zihao",      role: "Member",   title: "行銷負責人",      status: "away",    joined: "2025-11",  lastActive: "今日 14:20",    agents: 2, tasks: 9 },
  { id: "m5", n: "思明",   handle: "@siming",     role: "Member",   title: "客戶成功",        status: "online",  joined: "2026-01",  lastActive: "現在",          agents: 3, tasks: 7 },
  { id: "m6", n: "Barry",  handle: "@barry",      role: "Owner",    title: "產品設計師",      status: "online",  joined: "2025-08",  lastActive: "現在 · 你",     agents: 5, tasks: 22, me: true },
  { id: "m7", n: "Sarah",  handle: "@sarah",      role: "Guest",    title: "Acme · 外部協作", status: "offline", joined: "2026-03",  lastActive: "3 天前",        agents: 0, tasks: 2,  guest: true },
];

const PENDING_INVITES = [
  { id: "i1", email: "kevin@zenos.tw",   role: "Member", sentBy: "品瑄",  sentAt: "2 天前",  status: "pending" },
  { id: "i2", email: "laura@acme.com",   role: "Guest",  sentBy: "Barry", sentAt: "1 天前",  status: "pending" },
  { id: "i3", email: "tomohiro@hana.jp", role: "Member", sentBy: "品瑄",  sentAt: "昨天",    status: "opened" },
];

function InkTeamPage({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [tab, setTab] = useTeamS("members");

  const memberCount = MEMBERS.filter(m => !m.guest).length;
  const guestCount  = MEMBERS.filter(m => m.guest).length;

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="TEAM · 團隊" title="團隊" en="Team"
        subtitle="成員、權限、邀請，以及團隊層級的工作節律。"
        right={<div style={{ display: "flex", gap: 10 }}>
          <Btn t={t} variant="ghost" size="sm" icon={Icons.settings}>團隊設定</Btn>
          <Btn t={t} variant="seal"  size="sm" icon={Icons.plus}>邀請成員</Btn>
        </div>}
      />

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}`, marginBottom: 24 }}>
        {[
          { k: "成員",       v: memberCount.toString(),             sub: `${MEMBERS.filter(m => m.status === "online" && !m.guest).length} 人在線` },
          { k: "外部 Guest", v: guestCount.toString(),              sub: "客戶 · 承包商" },
          { k: "待回邀請",   v: PENDING_INVITES.length.toString(),  sub: "2 未讀 · 1 已讀" },
          { k: "席位用量",   v: "6 / 10",                            sub: "小隊方案" },
        ].map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>{s.k}</div>
            <div style={{ fontFamily: fontHead, fontSize: 28, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: 20, borderBottom: `1px solid ${c.inkHair}` }}>
        {[
          ["members", "成員", MEMBERS.length],
          ["invites", "邀請", PENDING_INVITES.length],
          ["roles",   "權限", 4],
          ["billing", "席位 · 帳務", null],
        ].map(([k, l, n]) => (
          <button key={k} onClick={() => setTab(k)} style={{
            padding: "10px 18px", background: "transparent", border: "none",
            borderBottom: tab === k ? `2px solid ${c.vermillion}` : "2px solid transparent",
            marginBottom: -1, cursor: "pointer", fontFamily: fontBody, fontSize: 13,
            color: tab === k ? c.ink : c.inkMuted,
            fontWeight: tab === k ? 500 : 400, letterSpacing: "0.04em",
            display: "flex", alignItems: "center", gap: 8,
          }}>
            {l}
            {n != null && <span style={{
              fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
              padding: "1px 6px", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
            }}>{n}</span>}
          </button>
        ))}
      </div>

      {tab === "members" && <MembersTab t={t} />}
      {tab === "invites" && <InvitesTab t={t} />}
      {tab === "roles"   && <RolesTab t={t} />}
      {tab === "billing" && <BillingTab t={t} />}
    </div>
  );
}

// ─── Members tab ───────────────────────────────────────────────────────
function MembersTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [q, setQ] = useTeamS("");
  const [filter, setFilter] = useTeamS("all");

  const filtered = MEMBERS.filter(m => {
    if (filter === "members" && m.guest) return false;
    if (filter === "guests" && !m.guest) return false;
    if (filter === "admins" && !["Owner","Admin"].includes(m.role)) return false;
    if (q && !m.n.toLowerCase().includes(q.toLowerCase()) && !m.handle.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  const roleChip = (role) => {
    if (role === "Owner") return <Chip t={t} tone="accent" dot>Owner</Chip>;
    if (role === "Admin") return <Chip t={t} tone="accent">Admin</Chip>;
    if (role === "Guest") return <Chip t={t} tone="ocher" dot>Guest</Chip>;
    return <Chip t={t} tone="muted">Member</Chip>;
  };

  const statusDot = (status) => {
    const color = status === "online" ? c.jade : status === "away" ? c.ocher : c.inkFaint;
    return <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block" }} />;
  };

  return (
    <>
      {/* Filter bar */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 12px", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, flex: 1, maxWidth: 320 }}>
          <Icon d={Icons.search} size={13} style={{ color: c.inkFaint }} />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="搜尋姓名或 @handle" style={{
            flex: 1, background: "transparent", border: "none", outline: "none",
            color: c.ink, fontSize: 13, fontFamily: fontBody,
          }} />
        </div>
        <div style={{ display: "flex", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2 }}>
          {[["all","全部"],["members","成員"],["admins","管理員"],["guests","Guest"]].map(([k, l]) => (
            <button key={k} onClick={() => setFilter(k)} style={{
              padding: "5px 12px", background: filter === k ? c.ink : "transparent",
              color: filter === k ? c.paper : c.inkMuted, border: "none", borderRadius: 2,
              cursor: "pointer", fontSize: 12, fontFamily: fontBody, letterSpacing: "0.04em",
            }}>{l}</button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <Btn t={t} variant="ghost" size="sm" icon={Icons.filter}>進階篩選</Btn>
      </div>

      {/* Members table */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 140px 100px 140px 120px 40px",
          gap: 12, padding: "10px 16px",
          borderBottom: `1px solid ${c.inkHairBold}`,
          fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
          letterSpacing: "0.18em", textTransform: "uppercase",
        }}>
          <span>成員</span><span>角色</span><span>Agent</span><span>最後活動</span><span>加入</span><span></span>
        </div>
        {filtered.map((m, i) => (
          <div key={m.id} style={{
            display: "grid", gridTemplateColumns: "1fr 140px 100px 140px 120px 40px",
            gap: 12, alignItems: "center",
            padding: "14px 16px",
            borderBottom: i < filtered.length - 1 ? `1px solid ${c.inkHair}` : "none",
            background: m.me ? c.paperWarm : "transparent",
            borderLeft: m.me ? `2px solid ${c.vermillion}` : "2px solid transparent",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: m.me ? c.vermSoft : c.paperWarm,
                border: `1px solid ${m.me ? c.vermLine : c.inkHair}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: fontHead, fontSize: 13, fontWeight: 500,
                color: m.me ? c.vermillion : c.inkSoft,
                position: "relative", flexShrink: 0,
              }}>
                {m.n[0]}
                <span style={{
                  position: "absolute", right: -2, bottom: -2,
                  width: 10, height: 10, borderRadius: "50%",
                  background: m.status === "online" ? c.jade : m.status === "away" ? c.ocher : c.inkFaint,
                  border: `2px solid ${m.me ? c.paperWarm : c.surface}`,
                }} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, color: c.ink, fontWeight: 500, letterSpacing: "0.02em" }}>
                  {m.n}
                  {m.me && <span style={{ fontFamily: fontMono, fontSize: 9, color: c.vermillion, marginLeft: 6, letterSpacing: "0.2em" }}>YOU</span>}
                </div>
                <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, marginTop: 2, letterSpacing: "0.02em" }}>
                  {m.handle} · <span style={{ fontFamily: fontBody }}>{m.title}</span>
                </div>
              </div>
            </div>
            <div>{roleChip(m.role)}</div>
            <div style={{ fontFamily: fontMono, fontSize: 12, color: c.inkSoft }}>
              {m.agents} 個
            </div>
            <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.02em", display: "flex", alignItems: "center", gap: 6 }}>
              {statusDot(m.status)} {m.lastActive}
            </div>
            <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkFaint, letterSpacing: "0.04em" }}>
              {m.joined}
            </div>
            <button style={{
              background: "transparent", border: "none", color: c.inkMuted,
              cursor: "pointer", padding: 6, borderRadius: 2,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon d="M12 5v.01M12 12v.01M12 19v.01" size={16} />
            </button>
          </div>
        ))}
      </div>
    </>
  );
}

// ─── Invites tab ───────────────────────────────────────────────────────
function InvitesTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}>
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ padding: "14px 18px", borderBottom: `1px solid ${c.inkHair}`, display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontFamily: fontHead, fontSize: 14, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>待回覆邀請</div>
          <div style={{ flex: 1 }} />
          <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em" }}>{PENDING_INVITES.length} PENDING</span>
        </div>
        {PENDING_INVITES.map((inv, i) => (
          <div key={inv.id} style={{
            display: "grid", gridTemplateColumns: "1fr 100px 120px 140px 120px",
            gap: 12, alignItems: "center",
            padding: "14px 18px",
            borderBottom: i < PENDING_INVITES.length - 1 ? `1px solid ${c.inkHair}` : "none",
          }}>
            <div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.ink, letterSpacing: "0.02em" }}>{inv.email}</div>
              <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 3 }}>由 {inv.sentBy} · {inv.sentAt} 寄出</div>
            </div>
            <Chip t={t} tone={inv.role === "Guest" ? "ocher" : "muted"} dot={inv.role === "Guest"}>{inv.role}</Chip>
            <Chip t={t} tone={inv.status === "opened" ? "accent" : "muted"} dot>
              {inv.status === "opened" ? "已讀" : "未讀"}
            </Chip>
            <div style={{ display: "flex", gap: 6 }}>
              <Btn t={t} variant="ghost" size="sm">重寄</Btn>
              <Btn t={t} variant="ghost" size="sm">複製鏈結</Btn>
            </div>
            <button style={{
              background: "transparent", border: "none", color: c.seal,
              cursor: "pointer", fontFamily: fontBody, fontSize: 12,
              textAlign: "right", padding: 0,
            }}>撤回</button>
          </div>
        ))}
        {PENDING_INVITES.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: c.inkFaint, fontSize: 13 }}>
            沒有待回覆的邀請。
          </div>
        )}
      </div>

      {/* Quick invite panel */}
      <div style={{ background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 20, alignSelf: "flex-start" }}>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
          QUICK INVITE · 快速邀請
        </div>
        <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em", marginBottom: 18 }}>
          邀請新夥伴
        </div>

        <div style={{ fontSize: 12, color: c.inkMuted, marginBottom: 6 }}>Email</div>
        <input placeholder="name@company.com" style={{
          width: "100%", padding: "8px 10px", marginBottom: 14,
          background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
          color: c.ink, fontSize: 13, fontFamily: fontBody, outline: "none",
        }} />

        <div style={{ fontSize: 12, color: c.inkMuted, marginBottom: 6 }}>角色</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
          {[
            { k: "Admin",  desc: "可管理成員、Agent、計費" },
            { k: "Member", desc: "可存取所有工作區與資料" },
            { k: "Guest",  desc: "僅能存取被指派的專案" },
          ].map(r => (
            <label key={r.k} style={{
              display: "flex", alignItems: "flex-start", gap: 10,
              padding: 10, background: c.surface,
              border: `1px solid ${r.k === "Member" ? c.vermLine : c.inkHair}`,
              borderRadius: 2, cursor: "pointer",
            }}>
              <input type="radio" name="role" defaultChecked={r.k === "Member"} style={{ marginTop: 3, accentColor: c.vermillion }} />
              <div>
                <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{r.k}</div>
                <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{r.desc}</div>
              </div>
            </label>
          ))}
        </div>

        <div style={{ fontSize: 12, color: c.inkMuted, marginBottom: 6 }}>附加訊息 · 可選</div>
        <textarea placeholder="來和我們一起共筆吧。" rows={3} style={{
          width: "100%", padding: "8px 10px", marginBottom: 16,
          background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
          color: c.ink, fontSize: 13, fontFamily: fontBody, outline: "none", resize: "vertical",
        }} />

        <Btn t={t} variant="ink" size="md" icon={Icons.plus} style={{ width: "100%", justifyContent: "center" }}>
          寄出邀請
        </Btn>
      </div>
    </div>
  );
}

// ─── Roles tab ─────────────────────────────────────────────────────────
function RolesTab({ t }) {
  const { c, fontHead, fontMono } = t;
  const roles = [
    { k: "Owner",  zh: "擁有者",  count: 2, color: c.vermillion },
    { k: "Admin",  zh: "管理員",  count: 1, color: c.ink },
    { k: "Member", zh: "成員",    count: 3, color: c.inkSoft },
    { k: "Guest",  zh: "訪客",    count: 1, color: c.ocher },
  ];
  const perms = [
    { g: "知識地圖",     items: [
      { p: "瀏覽",                     r: ["Owner","Admin","Member","Guest"] },
      { p: "編輯節點與關聯",           r: ["Owner","Admin","Member"] },
      { p: "刪除節點",                 r: ["Owner","Admin"] },
    ]},
    { g: "Agent · MCP",  items: [
      { p: "使用 Agent 工作區",       r: ["Owner","Admin","Member","Guest"] },
      { p: "建立自訂 Agent",          r: ["Owner","Admin","Member"] },
      { p: "管理 MCP 連線",            r: ["Owner","Admin"] },
    ]},
    { g: "團隊與計費",    items: [
      { p: "邀請成員",                 r: ["Owner","Admin"] },
      { p: "變更角色",                 r: ["Owner","Admin"] },
      { p: "變更方案 / 計費",          r: ["Owner"] },
      { p: "刪除工作區",               r: ["Owner"] },
    ]},
  ];
  const has = (role, allowed) => allowed.includes(role);
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 22 }}>
        {roles.map(r => (
          <div key={r.k} style={{
            padding: 16, background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
            borderTop: `2px solid ${r.color}`,
          }}>
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.22em", marginBottom: 4 }}>ROLE</div>
            <div style={{ fontFamily: fontHead, fontSize: 18, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>{r.zh}</div>
            <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, marginTop: 4, letterSpacing: "0.08em" }}>
              {r.k} · {r.count} 人
            </div>
          </div>
        ))}
      </div>

      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1fr repeat(4, 90px)", gap: 12,
          padding: "12px 18px", borderBottom: `1px solid ${c.inkHairBold}`,
          fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase",
        }}>
          <span>權限</span>
          {roles.map(r => <span key={r.k} style={{ textAlign: "center" }}>{r.k}</span>)}
        </div>
        {perms.map((g, gi) => (
          <div key={gi}>
            <div style={{
              padding: "10px 18px", background: c.paperWarm,
              borderBottom: `1px solid ${c.inkHair}`,
              fontFamily: fontHead, fontSize: 12, fontWeight: 500, color: c.ink,
              letterSpacing: "0.08em",
            }}>{g.g}</div>
            {g.items.map((p, pi) => (
              <div key={pi} style={{
                display: "grid", gridTemplateColumns: "1fr repeat(4, 90px)", gap: 12,
                padding: "11px 18px", alignItems: "center",
                borderBottom: (gi === perms.length - 1 && pi === g.items.length - 1) ? "none" : `1px solid ${c.inkHair}`,
                fontSize: 13, color: c.ink,
              }}>
                <span>{p.p}</span>
                {roles.map(r => (
                  <span key={r.k} style={{ textAlign: "center" }}>
                    {has(r.k, p.r) ? (
                      <span style={{ color: r.color }}>
                        <Icon d={Icons.check} size={16} stroke={2} />
                      </span>
                    ) : (
                      <span style={{ color: c.inkHair, fontFamily: fontMono, fontSize: 14 }}>—</span>
                    )}
                  </span>
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Billing tab ───────────────────────────────────────────────────────
function BillingTab({ t }) {
  const { c, fontHead, fontMono } = t;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 22 }}>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 6 }}>
          PLAN · 方案
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <div style={{ fontFamily: fontHead, fontSize: 26, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>小隊 · Team</div>
          <Chip t={t} tone="accent">推薦</Chip>
        </div>
        <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 6, lineHeight: 1.7 }}>
          10 席位 · 無限 Agent · 進階知識地圖
        </div>

        <div style={{ marginTop: 22, padding: 14, background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: c.inkMuted }}>席位用量</span>
            <span style={{ fontFamily: fontMono, fontSize: 12, color: c.ink }}>6 / 10</span>
          </div>
          <div style={{ height: 6, background: c.inkHair, borderRadius: 2 }}>
            <div style={{ width: "60%", height: "100%", background: c.vermillion, borderRadius: 2 }} />
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em", marginTop: 10 }}>
            下次計費 · 2026 / 05 / 15
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
          <Btn t={t} variant="outline" size="sm">加購席位</Btn>
          <Btn t={t} variant="ghost"   size="sm">變更方案</Btn>
          <Btn t={t} variant="ghost"   size="sm">發票紀錄</Btn>
        </div>
      </div>

      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 22 }}>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.22em", textTransform: "uppercase", marginBottom: 14 }}>
          USAGE THIS MONTH · 本月用量
        </div>
        {[
          { l: "Agent 執行次數",   v: "2,847",  cap: "5,000",   pct: 57 },
          { l: "儲存空間",         v: "4.2 GB", cap: "20 GB",   pct: 21 },
          { l: "知識節點",         v: "1,240",  cap: "無限",    pct: null },
          { l: "MCP 外部連線",     v: "12",     cap: "無限",    pct: null },
        ].map((x, i) => (
          <div key={i} style={{ padding: "11px 0", borderBottom: i < 3 ? `1px solid ${c.inkHair}` : "none" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: 12.5, color: c.ink }}>{x.l}</span>
              <span style={{ fontFamily: fontMono, fontSize: 12, color: c.inkMuted }}>
                <span style={{ color: c.ink }}>{x.v}</span> / {x.cap}
              </span>
            </div>
            {x.pct != null && (
              <div style={{ height: 3, background: c.inkHair, borderRadius: 2 }}>
                <div style={{ width: x.pct + "%", height: "100%", background: x.pct > 80 ? c.seal : c.ink, borderRadius: 2 }} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

window.InkTeamPage = InkTeamPage;
