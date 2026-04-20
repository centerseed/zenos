// ZenOS v2 · Agent · MCP — 重寫版：符合 .claude/ 實際架構
//   Skills = 角色（Architect / Developer / QA / PM / Designer / Marketing / ...）
//   MCP    = zenos (HTTP) + zenos-local (stdio)，暴露 mcp__zenos__* tools
//   Tasks  = todo → in_progress → review → confirm → done
//   Journal = mcp__zenos__journal_read/write 軌跡
const { useState: useAgS } = React;

// ─── Data：直接對應 .claude/skills/manifest.json + mcp.json + settings.json ─
const SKILLS = [
  // roles
  { name: "architect",  ver: "0.8.0", kind: "role",     owner: "Barry", desc: "系統架構、任務分配、subagent 調度、交付審查。", calls: ["mcp__zenos__task", "mcp__zenos__confirm", "mcp__zenos__journal_read", "mcp__zenos__plan"], runs7d: 42 },
  { name: "developer",  ver: "0.4.0", kind: "role",     owner: "Barry", desc: "按 Architect 技術設計實作功能。隔離 context 執行。",  calls: ["Read", "Glob", "Grep", "Write", "Edit", "Bash(cat:*)"], runs7d: 87 },
  { name: "qa",         ver: "0.4.0", kind: "role",     owner: "Barry", desc: "驗收 Developer 交付，產出 PASS / CONDITIONAL / FAIL。", calls: ["mcp__zenos__task", "Read", "Glob", "Grep"], runs7d: 63 },
  { name: "pm",         ver: "0.4.0", kind: "role",     owner: "Barry", desc: "需求整理、里程碑、優先序、backlog 治理。", calls: ["mcp__zenos__search", "mcp__zenos__task", "mcp__zenos__plan"], runs7d: 18 },
  { name: "designer",   ver: "0.2.0", kind: "role",     owner: "Barry", desc: "UI/UX 規劃、設計規格、視覺系統維護。", calls: ["mcp__zenos__search", "mcp__zenos__write"], runs7d: 11 },
  { name: "marketing",  ver: "0.2.0", kind: "role",     owner: "Barry", desc: "情報 / 生成 / 適配 / 發佈的行銷流程。", calls: ["mcp__zenos__search", "mcp__zenos__write", "mcp__zenos__analyze"], runs7d: 6 },
  { name: "challenger", ver: "0.2.0", kind: "role",     owner: "Barry", desc: "對決策與設計提出反對意見、找出盲點。", calls: ["mcp__zenos__search", "mcp__zenos__find_gaps"], runs7d: 4 },
  { name: "debugger",   ver: "0.1.0", kind: "role",     owner: "Barry", desc: "錯誤根因定位、二分搜尋、最小重現。", calls: ["Read", "Grep", "Bash(cat:*)"], runs7d: 9 },
  // governance skills (zenos-*)
  { name: "zenos-setup",      ver: "2.0.0", kind: "governance", owner: "Barry", desc: "初始化 workspace、skill 同步、版本管理。", calls: ["mcp__zenos__setup", "mcp__zenos__list_workspaces"], runs7d: 2 },
  { name: "zenos-capture",    ver: "2.2.0", kind: "governance", owner: "Barry", desc: "從對話擷取決策 / 設計 / 任務並寫入 SSOT。", calls: ["mcp__zenos__write", "mcp__zenos__upload_attachment"], runs7d: 28 },
  { name: "zenos-sync",       ver: "3.2.0", kind: "governance", owner: "Barry", desc: "本地 skills ↔ SSOT 雙向同步。", calls: ["mcp__zenos__batch_update_sources"], runs7d: 5 },
  { name: "zenos-governance", ver: "2.0.0", kind: "governance", owner: "Barry", desc: "文件 / L2 概念 / 任務治理規則載入器。", calls: ["mcp__zenos__governance_guide", "mcp__zenos__suggest_policy"], runs7d: 12 },
  // workflows
  { name: "feature",    ver: "1.0.0", kind: "workflow", owner: "Barry", desc: "新功能全流程：PM → Architect → Developer → QA → confirm。", calls: ["architect","developer","qa","pm"], runs7d: 3 },
  { name: "debug",      ver: "1.0.0", kind: "workflow", owner: "Barry", desc: "錯誤調查流程：Debugger → Developer → QA。", calls: ["debugger","developer","qa"], runs7d: 7 },
  { name: "triage",     ver: "1.0.0", kind: "workflow", owner: "Barry", desc: "Backlog 分類 / 優先序調整。", calls: ["pm","architect"], runs7d: 1 },
  { name: "brainstorm", ver: "1.0.0", kind: "workflow", owner: "Barry", desc: "多角色腦力激盪：PM + Architect + Challenger。", calls: ["pm","architect","challenger"], runs7d: 2 },
];

// MCP servers — 從 .claude/mcp.json
const MCP_SERVERS = [
  {
    id: "zenos",
    type: "http",
    url: "https://example.com/mcp?api_key=tok",
    status: "connected",
    latencyMs: 84,
    toolsExposed: 18,
    lastCall: "14:32 · journal_read",
    cwd: null,
    env: null,
  },
  {
    id: "zenos-local",
    type: "stdio",
    command: "/Users/wubaizong/clients/ZenOS/.venv/bin/python",
    args: ["-m", "zenos.interface.tools"],
    cwd: "/Users/wubaizong/clients/ZenOS",
    env: {
      GITHUB_TOKEN: "ghp_ptG***4SDF",
      GOOGLE_CLOUD_PROJECT: "zenos-naruvia",
      MCP_TRANSPORT: "stdio",
    },
    status: "connected",
    latencyMs: 12,
    toolsExposed: 18,
    lastCall: "14:31 · task(action=update)",
  },
];

// zenos tools — 從 allowedTools
const ZENOS_TOOLS = [
  { name: "search",              group: "query",      desc: "檢索 entities / tasks / docs。",            calls7d: 124 },
  { name: "get",                 group: "query",      desc: "取單一節點的完整資料。",                  calls7d: 312 },
  { name: "analyze",             group: "query",      desc: "關聯 / 影響 / 依賴分析。",                  calls7d: 48 },
  { name: "common_neighbors",    group: "query",      desc: "找兩個節點的共同鄰居。",                  calls7d: 11 },
  { name: "find_gaps",           group: "query",      desc: "找知識圖譜缺口 / 盲點。",                  calls7d: 9 },
  { name: "list_workspaces",     group: "query",      desc: "列出可用 workspaces。",                    calls7d: 3 },
  { name: "journal_read",        group: "query",      desc: "讀工作日誌（脈絡恢復）。",                calls7d: 67 },
  { name: "read_source",         group: "query",      desc: "讀取 source（GitHub / Drive / URL）。",    calls7d: 22 },
  { name: "write",               group: "mutation",   desc: "寫入 entity / document。",                  calls7d: 41 },
  { name: "journal_write",       group: "mutation",   desc: "寫工作日誌條目。",                        calls7d: 38 },
  { name: "task",                group: "mutation",   desc: "建 / 更新 task（create / update）。",       calls7d: 54 },
  { name: "plan",                group: "mutation",   desc: "建立 / 更新計畫（milestone / goal）。",     calls7d: 14 },
  { name: "batch_update_sources",group: "mutation",   desc: "批次更新 source status（valid/stale/broken）。", calls7d: 2 },
  { name: "upload_attachment",   group: "mutation",   desc: "上傳附件並綁到 entity。",                 calls7d: 5 },
  { name: "confirm",             group: "gate",       desc: "Architect 最終驗收（accepted=True → done）。", calls7d: 16 },
  { name: "setup",               group: "admin",      desc: "workspace 初始化。",                      calls7d: 1 },
  { name: "governance_guide",    group: "admin",      desc: "回傳治理文件摘要（寫文件 / L2 / 任務前必讀）。", calls7d: 19 },
  { name: "suggest_policy",      group: "admin",      desc: "針對 workspace 建議治理策略。",           calls7d: 4 },
];

// Tasks — 狀態流 todo → in_progress → review → confirm → done
const TASK_QUEUE = [
  { id: "T-0248", status: "review",       title: "驗證 CRM briefing live 端點的錯誤重試",         assignee: "qa",        linked: ["SPEC-briefing"], pri: "high",     updated: "14:32" },
  { id: "T-0247", status: "review",       title: "補齊 knowledge-map 節點的 visibility 保護",     assignee: "qa",        linked: ["ADR-visibility"], pri: "critical", updated: "13:18" },
  { id: "T-0246", status: "in_progress",  title: "實作 MCP tool rate limit（per-workspace）",       assignee: "developer", linked: ["SPEC-rate-limit"], pri: "high",    updated: "14:05" },
  { id: "T-0245", status: "in_progress",  title: "重構 journal_write schema 支援 multi-actor",     assignee: "developer", linked: ["SPEC-journal-v2"], pri: "medium",  updated: "12:51" },
  { id: "T-0244", status: "todo",         title: "調查 find_gaps 在大圖上的效能",                  assignee: "debugger",  linked: [], pri: "medium",   updated: "昨日" },
  { id: "T-0243", status: "todo",         title: "撰寫 SPEC：subagent 隔離 context 的記憶體上限", assignee: "architect", linked: [], pri: "high",     updated: "昨日" },
  { id: "T-0242", status: "todo",         title: "行銷 agent 的 adapt.md prompt 改寫",             assignee: "marketing", linked: [], pri: "low",      updated: "昨日" },
];

// Journal — mcp__zenos__journal_read 的最近條目
const JOURNAL = [
  { t: "14:32", actor: "qa",        kind: "verdict",  body: "T-0248 PASS — 重試已覆蓋 503 / timeout / DNS。",     task: "T-0248" },
  { t: "14:28", actor: "developer", kind: "commit",   body: "Fix: briefing-live 的 AbortController leak。",      task: "T-0248" },
  { t: "14:05", actor: "developer", kind: "progress", body: "T-0246 schema migration 完成，本地測試通過。",       task: "T-0246" },
  { t: "13:18", actor: "qa",        kind: "verdict",  body: "T-0247 PASS — visibility matrix 覆蓋 3 種 role。", task: "T-0247" },
  { t: "12:51", actor: "architect", kind: "dispatch", body: "派發 T-0245 → developer（SPEC ready，context 已隔離）。", task: "T-0245" },
  { t: "12:40", actor: "architect", kind: "decision", body: "決定：journal_write 改 schema v2（multi-actor）。",  task: "T-0245" },
  { t: "11:04", actor: "pm",        kind: "triage",   body: "T-0244 降優先到 medium（impact 已經被 T-0246 cover 一部分）。", task: "T-0244" },
  { t: "09:48", actor: "challenger",kind: "pushback", body: "質疑 subagent 隔離策略在 feature workflow 的回收時機。", task: "T-0243" },
];

// ─── Page ──────────────────────────────────────────────────────────────
function InkAgentPage({ t }) {
  const { c, fontHead, fontMono } = t;
  const [tab, setTab] = useAgS("cli");

  const servers   = MCP_SERVERS.length;
  const tools     = ZENOS_TOOLS.length;
  const skills    = SKILLS.length;
  const openTasks = TASK_QUEUE.filter(x => x.status !== "done").length;

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="AGENT · 安裝與設定" title="Agent 安裝 · MCP · Skills" en="Setup"
        subtitle="先裝好本地 helper（claude CLI），再接 MCP servers，最後同步 agent／skill。"
        right={<div style={{ display: "flex", gap: 10 }}>
          <Btn t={t} variant="ghost"   size="sm" icon={Icons.doc}>mcp.json</Btn>
          <Btn t={t} variant="ghost"   size="sm" icon={Icons.doc}>settings.json</Btn>
          <Btn t={t} variant="outline" size="sm" icon={Icons.spark}>Reload skills</Btn>
        </div>}
      />

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, background: c.inkHair, border: `1px solid ${c.inkHair}`, marginBottom: 24 }}>
        {[
          { k: "LOCAL HELPER",      v: "running",      sub: "claude 1.0.42 · daemon" },
          { k: "MCP SERVERS",       v: servers + "",   sub: "1 http · 1 stdio" },
          { k: "SKILLS · manifest", v: skills + "",    sub: "8 roles · 4 gov · 4 workflow" },
        ].map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>{s.k}</div>
            <div style={{ fontFamily: fontHead, fontSize: 28, fontWeight: 500, color: c.ink, letterSpacing: "0.02em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2, fontFamily: fontMono, letterSpacing: "0.02em" }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: 20, borderBottom: `1px solid ${c.inkHair}`, overflowX: "auto" }}>
        {[
          ["cli",     "Local helper", "claude CLI",      null],
          ["mcp",     "MCP",          ".claude/mcp.json", MCP_SERVERS.length],
          ["skills",  "Agents & Skills", ".claude/skills", SKILLS.length],
        ].map(([k, label, sub, n]) => (
          <button key={k} onClick={() => setTab(k)} style={{
            padding: "8px 16px", background: "transparent", border: "none",
            borderBottom: tab === k ? `2px solid ${c.vermillion}` : "2px solid transparent",
            marginBottom: -1, cursor: "pointer",
            color: tab === k ? c.ink : c.inkMuted,
            display: "flex", alignItems: "center", gap: 8,
            whiteSpace: "nowrap", flexShrink: 0,
          }}>
            <div style={{ textAlign: "left" }}>
              <div style={{
                fontFamily: fontHead, fontSize: 13, letterSpacing: "0.04em",
                fontWeight: tab === k ? 600 : 500,
              }}>{label}</div>
              <div style={{
                fontFamily: fontMono, fontSize: 9, color: c.inkFaint,
                letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 1,
              }}>{sub}</div>
            </div>
            {n != null && <span style={{
              fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
              padding: "1px 6px", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
            }}>{n}</span>}
          </button>
        ))}
      </div>

      {tab === "cli"    && <LocalHelperTab t={t} />}
      {tab === "mcp"    && <MCPServersTab t={t} />}
      {tab === "skills" && <SkillsTab t={t} />}
    </div>
  );
}

// ─── Skills ────────────────────────────────────────────────────────────
function SkillsTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [sel, setSel] = useAgS("architect");
  const [kind, setKind] = useAgS("all");

  const filtered = SKILLS.filter(s => kind === "all" || s.kind === kind);
  const active = SKILLS.find(s => s.name === sel) || SKILLS[0];

  const kindMeta = {
    role:       { fg: c.vermillion, bg: c.vermSoft,  label: "role" },
    governance: { fg: c.ocher,      bg: c.surface,   label: "governance" },
    workflow:   { fg: c.jade,       bg: c.surface,   label: "workflow" },
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 440px", gap: 20 }}>
      <div>
        <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center" }}>
          <div style={{ display: "flex", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2 }}>
            {[["all","all"],["role","role"],["governance","governance"],["workflow","workflow"]].map(([k, l]) => (
              <button key={k} onClick={() => setKind(k)} style={{
                padding: "5px 12px", background: kind === k ? c.ink : "transparent",
                color: kind === k ? c.paper : c.inkMuted, border: "none", borderRadius: 2,
                cursor: "pointer", fontSize: 11, fontFamily: fontMono, letterSpacing: "0.06em",
              }}>{l}</button>
            ))}
          </div>
          <div style={{ flex: 1 }} />
          <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em", textTransform: "uppercase" }}>
            publisher · ZenOS Platform · owner · Barry
          </span>
        </div>

        <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
          <div style={{
            display: "grid", gridTemplateColumns: "28px 1fr 110px 80px 80px",
            gap: 10, padding: "10px 16px",
            borderBottom: `1px solid ${c.inkHairBold}`,
            fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
            letterSpacing: "0.16em", textTransform: "uppercase",
          }}>
            <span></span><span>SKILL · description</span><span>KIND</span><span>VERSION</span><span>RUNS · 7d</span>
          </div>
          {filtered.map((s, i) => {
            const isSel = s.name === sel;
            const km = kindMeta[s.kind];
            return (
              <button key={s.name} onClick={() => setSel(s.name)} style={{
                display: "grid", gridTemplateColumns: "28px 1fr 110px 80px 80px",
                gap: 10, alignItems: "center", width: "100%",
                padding: "12px 16px",
                background: isSel ? c.paperWarm : "transparent",
                border: "none",
                borderLeft: isSel ? `2px solid ${c.vermillion}` : "2px solid transparent",
                borderBottom: i < filtered.length - 1 ? `1px solid ${c.inkHair}` : "none",
                cursor: "pointer", textAlign: "left", fontFamily: fontBody,
              }}>
                <span style={{ fontFamily: fontMono, fontSize: 14, color: km.fg }}>·</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontFamily: fontMono, fontSize: 13, color: c.ink, letterSpacing: "0.02em", fontWeight: 500 }}>
                    {s.name}
                  </div>
                  <div style={{ fontSize: 11.5, color: c.inkMuted, marginTop: 3, letterSpacing: "0.01em" }}>
                    {s.desc}
                  </div>
                </div>
                <span style={{
                  fontFamily: fontMono, fontSize: 10, color: km.fg,
                  padding: "2px 8px", background: km.bg,
                  border: `1px solid ${km.fg}44`, borderRadius: 2,
                  textTransform: "uppercase", letterSpacing: "0.12em",
                  justifySelf: "start",
                }}>{km.label}</span>
                <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkSoft }}>{s.ver}</span>
                <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted }}>{s.runs7d}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Detail */}
      <aside style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, alignSelf: "flex-start", position: "sticky", top: 20 }}>
        <div style={{ padding: "16px 20px 12px", borderBottom: `1px solid ${c.inkHair}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{
              fontFamily: fontMono, fontSize: 10, color: kindMeta[active.kind].fg,
              padding: "2px 7px", background: kindMeta[active.kind].bg,
              border: `1px solid ${kindMeta[active.kind].fg}44`, borderRadius: 2,
              letterSpacing: "0.14em", textTransform: "uppercase",
            }}>{active.kind}</span>
            <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em" }}>
              v{active.ver} · {active.owner}
            </span>
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 18, color: c.ink, letterSpacing: "0.02em", fontWeight: 500 }}>
            {active.name}
          </div>
          <div style={{ fontSize: 12.5, color: c.inkSoft, lineHeight: 1.7, marginTop: 8 }}>
            {active.desc}
          </div>
        </div>

        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${c.inkHair}` }}>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
            {active.kind === "workflow" ? "invokes" : "allowed calls"}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {active.calls.map(tool => (
              <div key={tool} style={{
                fontFamily: fontMono, fontSize: 11.5, color: c.ink,
                padding: "4px 10px", background: c.paperWarm,
                border: `1px solid ${c.inkHair}`, borderRadius: 2,
                letterSpacing: "0.02em", display: "flex", alignItems: "center", gap: 8,
              }}>
                <span style={{ color: c.vermillion }}>›</span>
                <span>{tool}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${c.inkHair}` }}>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
            path
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 11.5, color: c.inkSoft, letterSpacing: "0.02em" }}>
            .claude/skills/{active.name}/SKILL.md
          </div>
        </div>

        <div style={{ padding: "14px 20px", display: "flex", gap: 8 }}>
          <Btn t={t} variant="outline" size="sm" icon={Icons.doc} style={{ flex: 1, justifyContent: "center" }}>open SKILL.md</Btn>
          <Btn t={t} variant="ghost" size="sm">journal</Btn>
        </div>
      </aside>
    </div>
  );
}

// ─── MCP servers ───────────────────────────────────────────────────────
function MCPServersTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [editing, setEditing] = useAgS(null); // server id or "new" or null
  const [showJson, setShowJson] = useAgS(false);

  const jsonPreview = JSON.stringify({
    mcpServers: Object.fromEntries(MCP_SERVERS.map(s => [
      s.id,
      s.type === "http"
        ? { type: "http", url: s.url }
        : { type: "stdio", command: s.command, args: s.args, env: s.env, cwd: s.cwd },
    ])),
  }, null, 2);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.04em" }}>
          <span style={{ color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginRight: 8 }}>source</span>
          .claude/mcp.json
        </div>
        <div style={{ flex: 1 }} />
        <Btn t={t} variant="ghost"   size="sm" icon={Icons.doc} onClick={() => setShowJson(v => !v)}>
          {showJson ? "hide JSON" : "show JSON"}
        </Btn>
        <Btn t={t} variant="outline" size="sm" icon={Icons.plus} onClick={() => setEditing("new")}>新增 server</Btn>
      </div>

      {showJson && (
        <pre style={{
          background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
          padding: "14px 18px", marginBottom: 14,
          fontFamily: fontMono, fontSize: 11.5, color: c.inkSoft,
          letterSpacing: "0.02em", lineHeight: 1.6, overflow: "auto",
        }}>{jsonPreview}</pre>
      )}

      {editing && <MCPEditor t={t} id={editing} onClose={() => setEditing(null)} />}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {MCP_SERVERS.map(s => (
          <div key={s.id} style={{
            background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
            overflow: "hidden",
          }}>
            {/* header */}
            <div style={{ padding: "14px 18px", borderBottom: `1px solid ${c.inkHairBold}`, display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{
                width: 38, height: 38, borderRadius: 2,
                background: c.paperWarm, border: `1px solid ${c.inkHair}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: fontMono, fontSize: 11, color: c.vermillion, fontWeight: 600,
                letterSpacing: "0.08em",
              }}>{s.type.toUpperCase()}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: fontMono, fontSize: 15, color: c.ink, fontWeight: 500, letterSpacing: "0.02em" }}>
                  {s.id}
                </div>
                <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 3 }}>
                  MCP server · {s.type}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.jade, boxShadow: `0 0 0 3px ${c.jade}22` }} />
                <span style={{ fontFamily: fontMono, fontSize: 10, color: c.jade, letterSpacing: "0.14em", textTransform: "uppercase" }}>connected</span>
              </div>
            </div>

            {/* config */}
            <div style={{ padding: "12px 18px", borderBottom: `1px solid ${c.inkHair}`, background: c.paperWarm }}>
              {s.type === "http" ? (
                <Row t={t} k="url" v={s.url} mono />
              ) : (
                <>
                  <Row t={t} k="command" v={s.command} mono />
                  <Row t={t} k="args" v={s.args.join(" ")} mono />
                  <Row t={t} k="cwd" v={s.cwd} mono />
                </>
              )}
            </div>

            {/* env */}
            {s.env && (
              <div style={{ padding: "12px 18px", borderBottom: `1px solid ${c.inkHair}` }}>
                <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
                  env
                </div>
                {Object.entries(s.env).map(([k, v]) => (
                  <div key={k} style={{
                    display: "grid", gridTemplateColumns: "180px 1fr", gap: 8,
                    fontFamily: fontMono, fontSize: 11, padding: "3px 0",
                  }}>
                    <span style={{ color: c.inkMuted }}>{k}</span>
                    <span style={{ color: c.ink, letterSpacing: "0.02em" }}>{v}</span>
                  </div>
                ))}
              </div>
            )}

            {/* stats */}
            <div style={{ padding: "12px 18px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              {[
                { k: "tools exposed", v: s.toolsExposed },
                { k: "latency p50",   v: s.latencyMs + "ms" },
                { k: "last call",     v: s.lastCall, small: true },
              ].map(x => (
                <div key={x.k}>
                  <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 3 }}>{x.k}</div>
                  <div style={{ fontFamily: fontMono, fontSize: x.small ? 11 : 15, color: c.ink, fontWeight: x.small ? 400 : 500, letterSpacing: "0.02em" }}>{x.v}</div>
                </div>
              ))}
            </div>

            <div style={{ padding: "10px 18px", borderTop: `1px solid ${c.inkHair}`, display: "flex", gap: 8 }}>
              <Btn t={t} variant="ghost" size="sm">ping</Btn>
              <Btn t={t} variant="ghost" size="sm">list tools</Btn>
              <Btn t={t} variant="ghost" size="sm">logs</Btn>
              <div style={{ flex: 1 }} />
              <Btn t={t} variant="ghost" size="sm" onClick={() => setEditing(s.id)}>編輯</Btn>
              <Btn t={t} variant="ghost" size="sm">restart</Btn>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MCP Editor ────────────────────────────────────────────────────────
function MCPEditor({ t, id, onClose }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const existing = MCP_SERVERS.find(s => s.id === id);
  const isNew = id === "new";
  const [kind, setKind] = useAgS(existing?.type || "stdio");
  const [form, setForm] = useAgS(existing || {
    id: "my-server", type: "stdio",
    command: "/usr/bin/python", args: ["-m", "my_package"], cwd: "",
    env: {}, url: "",
  });
  const up = (k, v) => setForm({ ...form, [k]: v });

  return (
    <div style={{
      background: c.surface, border: `1px solid ${c.inkHairBold}`, borderRadius: 2,
      padding: "18px 22px", marginBottom: 14, position: "relative",
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
        <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
          {isNew ? "新增 MCP server" : `編輯 · ${existing?.id}`}
        </div>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>
          mcp.json · mcpServers.{form.id}
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={onClose} style={{ background: "transparent", border: "none", color: c.inkMuted, cursor: "pointer", fontSize: 18 }}>×</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "14px 16px", alignItems: "center" }}>
        <Lbl t={t}>id</Lbl>
        <Inp t={t} value={form.id} onChange={v => up("id", v)} mono />

        <Lbl t={t}>transport</Lbl>
        <div style={{ display: "flex", background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2, width: "fit-content" }}>
          {["stdio", "http", "sse"].map(k => (
            <button key={k} onClick={() => setKind(k)} style={{
              padding: "5px 14px", background: kind === k ? c.ink : "transparent",
              color: kind === k ? c.paper : c.inkMuted, border: "none", borderRadius: 2,
              cursor: "pointer", fontSize: 11, fontFamily: fontMono, letterSpacing: "0.08em",
            }}>{k}</button>
          ))}
        </div>

        {kind === "stdio" ? (
          <>
            <Lbl t={t}>command</Lbl>
            <Inp t={t} value={form.command || ""} onChange={v => up("command", v)} mono placeholder="/usr/local/bin/python" />
            <Lbl t={t}>args</Lbl>
            <Inp t={t} value={(form.args || []).join(" ")} onChange={v => up("args", v.split(" ").filter(Boolean))} mono placeholder="-m my_package.server" />
            <Lbl t={t}>cwd</Lbl>
            <Inp t={t} value={form.cwd || ""} onChange={v => up("cwd", v)} mono placeholder="/Users/me/project" />
          </>
        ) : (
          <>
            <Lbl t={t}>url</Lbl>
            <Inp t={t} value={form.url || ""} onChange={v => up("url", v)} mono placeholder="https://example.com/mcp" />
          </>
        )}

        <Lbl t={t} align="start">env</Lbl>
        <EnvEditor t={t} env={form.env || {}} onChange={e => up("env", e)} />
      </div>

      <div style={{ marginTop: 18, display: "flex", gap: 8, paddingTop: 14, borderTop: `1px solid ${c.inkHair}` }}>
        <Btn t={t} variant="ghost" size="sm">test connection</Btn>
        <div style={{ flex: 1 }} />
        <Btn t={t} variant="ghost" size="sm" onClick={onClose}>取消</Btn>
        {!isNew && <Btn t={t} variant="ghost" size="sm">刪除</Btn>}
        <Btn t={t} variant="seal" size="sm" onClick={onClose}>寫入 mcp.json</Btn>
      </div>
    </div>
  );
}

function Lbl({ t, children, align = "center" }) {
  return (
    <div style={{
      fontFamily: t.fontMono, fontSize: 10, color: t.c.inkFaint,
      letterSpacing: "0.2em", textTransform: "uppercase",
      alignSelf: align === "start" ? "flex-start" : "center",
      paddingTop: align === "start" ? 8 : 0,
    }}>{children}</div>
  );
}

function Inp({ t, value, onChange, mono, placeholder }) {
  const { c, fontMono, fontBody } = t;
  return (
    <input value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)}
      style={{
        padding: "7px 10px", background: c.paperWarm,
        border: `1px solid ${c.inkHair}`, borderRadius: 2,
        fontFamily: mono ? fontMono : fontBody, fontSize: 12,
        color: c.ink, letterSpacing: "0.02em", outline: "none",
      }}
      onFocus={e => e.target.style.borderColor = c.vermLine}
      onBlur={e => e.target.style.borderColor = c.inkHair}
    />
  );
}

function EnvEditor({ t, env, onChange }) {
  const { c, fontMono } = t;
  const entries = Object.entries(env);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {entries.map(([k, v], i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "180px 1fr 28px", gap: 6, alignItems: "center" }}>
          <input defaultValue={k} style={envInpStyle(c)} />
          <input defaultValue={v} style={envInpStyle(c)} />
          <button onClick={() => {
            const next = { ...env }; delete next[k]; onChange(next);
          }} style={{ background: "transparent", border: "none", color: c.inkMuted, cursor: "pointer", fontSize: 14 }}>×</button>
        </div>
      ))}
      <button onClick={() => onChange({ ...env, ["NEW_KEY_" + entries.length]: "" })} style={{
        padding: "5px 10px", background: "transparent",
        border: `1px dashed ${c.inkHair}`, borderRadius: 2,
        color: c.inkMuted, cursor: "pointer", fontFamily: fontMono, fontSize: 11,
        letterSpacing: "0.08em", alignSelf: "flex-start",
      }}>+ 新增 env 變數</button>
    </div>
  );
}
function envInpStyle(c) {
  return {
    padding: "5px 8px", background: c.paperWarm, border: `1px solid ${c.inkHair}`,
    borderRadius: 2, fontFamily: "ui-monospace, monospace", fontSize: 11.5,
    color: c.ink, letterSpacing: "0.02em", outline: "none",
  };
}

// ─── Local Helper (Claude Code CLI) ────────────────────────────────────
function LocalHelperTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [installed, setInstalled] = useAgS(true);
  const [vals, setVals] = useAgS({
    binPath: "/Users/wubaizong/.local/bin/claude",
    version: "1.0.42",
    cwd: "/Users/wubaizong/clients/ZenOS",
    autoRead: true,
    mcpFromProject: true,
    allowBashExec: false,
    daemon: true,
    socket: "~/.zenos/helper.sock",
    defaultModel: "sonnet",
  });
  const up = (k, v) => setVals({ ...vals, [k]: v });

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 18, maxWidth: 1040 }}>
      {/* Status banner */}
      <div style={{
        background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2,
        padding: "16px 20px", display: "flex", alignItems: "center", gap: 14,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 2,
          background: installed ? c.vermSoft : c.paperWarm,
          border: `1px solid ${installed ? c.vermLine : c.inkHair}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: fontMono, fontSize: 14, color: c.vermillion, fontWeight: 600,
          letterSpacing: "0.04em",
        }}>CC</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>
            Claude Code CLI helper
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.02em", marginTop: 3 }}>
            本地 agent 的執行代理。將 ZenOS UI 的動作轉為 `claude` 指令，讀 <span style={{ color: c.ink }}>.claude/</span> 設定、共用 mcp.json。
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: installed ? c.jade : c.inkFaint, boxShadow: installed ? `0 0 0 3px ${c.jade}22` : "none" }} />
          <span style={{ fontFamily: fontMono, fontSize: 11, color: installed ? c.jade : c.inkFaint, letterSpacing: "0.14em", textTransform: "uppercase" }}>
            {installed ? "running" : "not installed"}
          </span>
        </div>
      </div>

      {/* Install / Binary */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <HdrBlock t={t} title="安裝 · Binary" en="Installation">
          helper 會呼叫本地 <span style={{ fontFamily: fontMono, color: c.ink }}>claude</span> CLI；若未安裝，先跑下方指令。
        </HdrBlock>

        <div style={{ padding: "16px 22px", borderBottom: `1px solid ${c.inkHair}`, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {[
            { k: "binary path", v: vals.binPath, mono: true },
            { k: "version",     v: vals.version, mono: true },
            { k: "last check",  v: "2 分鐘前", mono: false },
          ].map(x => (
            <div key={x.k}>
              <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 5 }}>{x.k}</div>
              <div style={{ fontFamily: x.mono ? fontMono : fontBody, fontSize: 12.5, color: c.ink, letterSpacing: "0.02em", wordBreak: "break-all" }}>{x.v}</div>
            </div>
          ))}
        </div>

        <div style={{ padding: "14px 22px" }}>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
            install · curl
          </div>
          <CodeBlock t={t}>
            <span style={{ color: c.inkFaint }}>$ </span>curl -fsSL https://claude.ai/install.sh | sh
            {"\n"}
            <span style={{ color: c.inkFaint }}>$ </span>claude --version
            {"\n"}
            <span style={{ color: c.inkMuted }}>  claude 1.0.42</span>
          </CodeBlock>

          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <Btn t={t} variant="outline" size="sm" icon={Icons.spark}>檢查更新</Btn>
            <Btn t={t} variant="ghost"   size="sm">重新偵測路徑</Btn>
            <div style={{ flex: 1 }} />
            <Btn t={t} variant="ghost" size="sm">打開官方文件</Btn>
          </div>
        </div>
      </div>

      {/* Project binding */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <HdrBlock t={t} title="專案綁定 · Project" en="Project binding">
          helper 啟動時要把哪個目錄當成 workspace？這會決定 <span style={{ fontFamily: fontMono, color: c.ink }}>.claude/</span> 讀哪份。
        </HdrBlock>
        <div style={{ padding: "14px 22px", display: "grid", gridTemplateColumns: "140px 1fr 110px", gap: 14, alignItems: "center" }}>
          <Lbl t={t}>cwd</Lbl>
          <Inp t={t} value={vals.cwd} onChange={v => up("cwd", v)} mono />
          <Btn t={t} variant="ghost" size="sm">browse</Btn>
        </div>
        <div style={{ padding: "10px 22px 16px" }}>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8,
            padding: "10px 14px", background: c.paperWarm,
            border: `1px solid ${c.inkHair}`, borderRadius: 2,
          }}>
            {[
              { k: ".claude/mcp.json",           ok: true },
              { k: ".claude/settings.json",      ok: true },
              { k: ".claude/skills/manifest",    ok: true },
            ].map(x => (
              <div key={x.k} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: x.ok ? c.jade : c.seal }} />
                <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkSoft, letterSpacing: "0.02em" }}>{x.k}</span>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: x.ok ? c.jade : c.seal, letterSpacing: "0.14em", textTransform: "uppercase" }}>{x.ok ? "ok" : "missing"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Runtime */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <HdrBlock t={t} title="執行模式 · Runtime" en="Runtime">
          helper 如何被 ZenOS UI 呼叫。Daemon 模式會在背景待命，減少冷啟動。
        </HdrBlock>
        {[
          { k: "daemon", l: "常駐 daemon（推薦）", hint: "開啟後 UI 呼叫透過 unix socket，延遲 < 20ms。關閉則每次 spawn 新 process。" },
          { k: "autoRead", l: "自動讀 .claude/ 設定", hint: "helper 啟動時載入 skills / mcp / allowedTools。" },
          { k: "mcpFromProject", l: "使用專案的 mcp.json", hint: "關閉後改用 global helper 設定（~/.claude/mcp.json）。" },
          { k: "allowBashExec", l: "允許 Bash 執行（非白名單）", hint: "開啟後 agent 可跑任意 shell 指令；謹慎使用。" },
        ].map((r, i, arr) => (
          <div key={r.k} style={{
            display: "grid", gridTemplateColumns: "1fr auto", gap: 20,
            padding: "14px 22px", alignItems: "center",
            borderBottom: i < arr.length - 1 ? `1px solid ${c.inkHair}` : "none",
          }}>
            <div>
              <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{r.l}</div>
              <div style={{ fontSize: 11.5, color: c.inkMuted, marginTop: 3, lineHeight: 1.6 }}>{r.hint}</div>
            </div>
            <Toggle2 t={t} on={vals[r.k]} onChange={v => up(r.k, v)} />
          </div>
        ))}
        <div style={{ padding: "14px 22px", display: "grid", gridTemplateColumns: "140px 1fr 140px 120px", gap: 14, alignItems: "center", borderTop: `1px solid ${c.inkHair}` }}>
          <Lbl t={t}>socket</Lbl>
          <Inp t={t} value={vals.socket} onChange={v => up("socket", v)} mono />
          <Lbl t={t}>default model</Lbl>
          <div style={{ display: "flex", background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2 }}>
            {["haiku", "sonnet", "opus"].map(k => (
              <button key={k} onClick={() => up("defaultModel", k)} style={{
                flex: 1, padding: "5px 8px", background: vals.defaultModel === k ? c.ink : "transparent",
                color: vals.defaultModel === k ? c.paper : c.inkMuted, border: "none", borderRadius: 2,
                cursor: "pointer", fontSize: 11, fontFamily: fontMono, letterSpacing: "0.06em",
              }}>{k}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Quick commands */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <HdrBlock t={t} title="常用指令 · Commands" en="CLI commands">
          開發者手動操作 helper 用的指令。UI 上的動作最終會翻譯成這些。
        </HdrBlock>
        <div style={{ padding: "14px 22px", display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { cmd: "claude --version",                                            desc: "確認 CLI 可用" },
            { cmd: "claude mcp list",                                             desc: "列出已連線的 MCP servers" },
            { cmd: "claude mcp add zenos --type http --url https://…",            desc: "新增 MCP server" },
            { cmd: "claude /agents",                                              desc: "列出所有 subagent" },
            { cmd: "claude /skills",                                              desc: "列出所有 skill（和本頁一致）" },
            { cmd: "claude --cwd /Users/wubaizong/clients/ZenOS",                 desc: "在指定專案啟動" },
            { cmd: "claude -p 'architect: triage backlog'",                       desc: "直接派發任務給 architect agent" },
          ].map(x => (
            <div key={x.cmd} style={{
              display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "center",
              padding: "8px 12px", background: c.paperWarm,
              border: `1px solid ${c.inkHair}`, borderRadius: 2,
            }}>
              <div style={{ fontFamily: fontMono, fontSize: 11.5, color: c.ink, letterSpacing: "0.02em" }}>
                <span style={{ color: c.inkFaint }}>$ </span>{x.cmd}
              </div>
              <div style={{ fontSize: 11, color: c.inkMuted, letterSpacing: "0.02em" }}>{x.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HdrBlock({ t, title, en, children }) {
  const { c, fontHead, fontMono } = t;
  return (
    <div style={{ padding: "16px 22px", borderBottom: `1px solid ${c.inkHair}` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>{title}</div>
        <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>{en}</div>
      </div>
      <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 4, lineHeight: 1.6 }}>{children}</div>
    </div>
  );
}

function CodeBlock({ t, children }) {
  const { c, fontMono } = t;
  return (
    <pre style={{
      background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2,
      padding: "12px 14px", margin: 0,
      fontFamily: fontMono, fontSize: 11.5, color: c.ink,
      letterSpacing: "0.02em", lineHeight: 1.7, overflow: "auto",
    }}>{children}</pre>
  );
}

function Toggle2({ t, on, onChange }) {
  const { c } = t;
  return (
    <button onClick={() => onChange(!on)} style={{
      width: 40, height: 22, background: on ? c.vermillion : c.inkHair,
      border: "none", borderRadius: 12, cursor: "pointer", position: "relative",
      transition: "all .18s", flexShrink: 0,
    }}>
      <span style={{
        position: "absolute", top: 2, left: on ? 20 : 2,
        width: 18, height: 18, background: c.paper, borderRadius: "50%",
        transition: "all .18s",
      }} />
    </button>
  );
}

function Row({ t, k, v, mono }) {
  const { c, fontMono } = t;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "90px 1fr", gap: 10,
      fontFamily: fontMono, fontSize: 11, padding: "3px 0",
    }}>
      <span style={{ color: c.inkFaint, letterSpacing: "0.1em" }}>{k}</span>
      <span style={{ color: c.ink, letterSpacing: "0.02em", wordBreak: "break-all" }}>{v}</span>
    </div>
  );
}

// ─── Tools (allowedTools matrix) ───────────────────────────────────────
function ToolsTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [group, setGroup] = useAgS("all");
  const filtered = ZENOS_TOOLS.filter(x => group === "all" || x.group === group);

  const groupMeta = {
    query:    { fg: c.jade,       label: "query" },
    mutation: { fg: c.vermillion, label: "mutation" },
    gate:     { fg: c.seal,       label: "gate" },
    admin:    { fg: c.ocher,      label: "admin" },
  };

  const totalCalls = ZENOS_TOOLS.reduce((a, b) => a + b.calls7d, 0);

  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center" }}>
        <div style={{ display: "flex", background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2 }}>
          {[["all","all"],["query","query"],["mutation","mutation"],["gate","gate"],["admin","admin"]].map(([k, l]) => (
            <button key={k} onClick={() => setGroup(k)} style={{
              padding: "5px 12px", background: group === k ? c.ink : "transparent",
              color: group === k ? c.paper : c.inkMuted, border: "none", borderRadius: 2,
              cursor: "pointer", fontSize: 11, fontFamily: fontMono, letterSpacing: "0.06em",
            }}>{l}</button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.14em", textTransform: "uppercase" }}>
          total · {totalCalls.toLocaleString()} calls / 7d
        </span>
      </div>

      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <div style={{
          display: "grid", gridTemplateColumns: "2fr 3fr 100px 120px",
          gap: 12, padding: "10px 18px",
          borderBottom: `1px solid ${c.inkHairBold}`,
          fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
          letterSpacing: "0.16em", textTransform: "uppercase",
        }}>
          <span>tool</span><span>purpose</span><span>group</span><span>calls · 7d</span>
        </div>
        {filtered.map((tool, i) => {
          const gm = groupMeta[tool.group];
          return (
            <div key={tool.name} style={{
              display: "grid", gridTemplateColumns: "2fr 3fr 100px 120px",
              gap: 12, padding: "12px 18px", alignItems: "center",
              borderBottom: i < filtered.length - 1 ? `1px solid ${c.inkHair}` : "none",
              fontFamily: fontBody, fontSize: 12.5,
            }}>
              <div style={{ fontFamily: fontMono, fontSize: 12, color: c.ink, letterSpacing: "0.02em" }}>
                <span style={{ color: c.inkFaint }}>mcp__zenos__</span>
                <span style={{ fontWeight: 500 }}>{tool.name}</span>
              </div>
              <div style={{ color: c.inkSoft, letterSpacing: "0.02em" }}>{tool.desc}</div>
              <span style={{
                fontFamily: fontMono, fontSize: 10, color: gm.fg,
                padding: "2px 8px", border: `1px solid ${gm.fg}55`, borderRadius: 2,
                textTransform: "uppercase", letterSpacing: "0.12em", justifySelf: "start",
              }}>{gm.label}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ flex: 1, height: 3, background: c.inkHair, borderRadius: 2 }}>
                  <div style={{
                    width: Math.min(100, (tool.calls7d / 320) * 100) + "%",
                    height: "100%", background: gm.fg, borderRadius: 2,
                  }} />
                </div>
                <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, minWidth: 32, textAlign: "right" }}>{tool.calls7d}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{
        marginTop: 16, padding: "12px 18px",
        background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2,
        fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.02em",
      }}>
        <span style={{ color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginRight: 10 }}>note</span>
        上表為 zenos / zenos-local 兩個 server 合併視圖。同一工具會從兩個 prefix 曝光：
        <span style={{ color: c.ink, marginLeft: 6 }}>mcp__zenos__*</span>
        <span style={{ margin: "0 4px" }}>/</span>
        <span style={{ color: c.ink }}>mcp__claude_ai_zenos__*</span>
        ，settings.json 已同步授權兩組。
      </div>
    </div>
  );
}

// ─── Tasks ─────────────────────────────────────────────────────────────
function TasksTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [selStatus, setSelStatus] = useAgS("all");

  const statusMeta = {
    todo:        { fg: c.inkFaint,   label: "todo" },
    in_progress: { fg: c.vermillion, label: "in_progress" },
    review:      { fg: c.ocher,      label: "review" },
    done:        { fg: c.jade,       label: "done" },
  };

  const priMeta = {
    critical: c.seal,
    high:     c.vermillion,
    medium:   c.ocher,
    low:      c.inkFaint,
  };

  const filtered = TASK_QUEUE.filter(x => selStatus === "all" || x.status === selStatus);

  return (
    <div>
      {/* pipeline diagram */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: "14px 18px", marginBottom: 16 }}>
        <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
          state machine
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {[
            { k: "todo",        n: 3 },
            { k: "in_progress", n: 2 },
            { k: "review",      n: 2 },
            { k: "done",        n: "∞" },
          ].map((x, i, arr) => {
            const sm = statusMeta[x.k];
            return (
              <React.Fragment key={x.k}>
                <button onClick={() => setSelStatus(x.k)} style={{
                  padding: "8px 14px",
                  background: selStatus === x.k ? c.paperWarm : "transparent",
                  border: `1px solid ${selStatus === x.k ? sm.fg : c.inkHair}`,
                  borderRadius: 2, cursor: "pointer",
                  fontFamily: fontMono, fontSize: 12,
                  color: c.ink, letterSpacing: "0.02em",
                  display: "flex", alignItems: "center", gap: 8,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: sm.fg }} />
                  <span>{sm.label}</span>
                  <span style={{ color: c.inkFaint, fontSize: 11 }}>{x.n}</span>
                </button>
                {i < arr.length - 1 && (
                  <span style={{ color: c.inkFaint, fontFamily: fontMono, fontSize: 12 }}>→</span>
                )}
                {x.k === "review" && (
                  <span style={{ color: c.seal, fontFamily: fontMono, fontSize: 10, padding: "2px 6px", border: `1px solid ${c.seal}55`, borderRadius: 2, letterSpacing: "0.08em" }}>
                    confirm()
                  </span>
                )}
              </React.Fragment>
            );
          })}
          <div style={{ flex: 1 }} />
          <button onClick={() => setSelStatus("all")} style={{
            fontFamily: fontMono, fontSize: 11, color: selStatus === "all" ? c.ink : c.inkMuted,
            background: "transparent", border: "none", cursor: "pointer", letterSpacing: "0.06em",
            textDecoration: selStatus === "all" ? "underline" : "none",
          }}>show all</button>
        </div>
      </div>

      {/* task list */}
      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2 }}>
        <div style={{
          display: "grid", gridTemplateColumns: "80px 1fr 120px 110px 90px 80px",
          gap: 12, padding: "10px 18px",
          borderBottom: `1px solid ${c.inkHairBold}`,
          fontFamily: fontMono, fontSize: 10, color: c.inkFaint,
          letterSpacing: "0.16em", textTransform: "uppercase",
        }}>
          <span>id</span><span>title</span><span>assignee</span><span>status</span><span>priority</span><span>updated</span>
        </div>
        {filtered.map((tk, i) => {
          const sm = statusMeta[tk.status];
          return (
            <div key={tk.id} style={{
              display: "grid", gridTemplateColumns: "80px 1fr 120px 110px 90px 80px",
              gap: 12, padding: "12px 18px", alignItems: "center",
              borderBottom: i < filtered.length - 1 ? `1px solid ${c.inkHair}` : "none",
              fontFamily: fontBody, fontSize: 12.5,
            }}>
              <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.04em" }}>{tk.id}</span>
              <div style={{ minWidth: 0 }}>
                <div style={{ color: c.ink, fontWeight: 500 }}>{tk.title}</div>
                {tk.linked.length > 0 && (
                  <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
                    {tk.linked.map(l => (
                      <span key={l} style={{
                        fontFamily: fontMono, fontSize: 10, color: c.inkMuted,
                        padding: "1px 6px", border: `1px solid ${c.inkHair}`, borderRadius: 2,
                        letterSpacing: "0.04em",
                      }}>{l}</span>
                    ))}
                  </div>
                )}
              </div>
              <span style={{ fontFamily: fontMono, fontSize: 11.5, color: c.inkSoft, letterSpacing: "0.02em" }}>@{tk.assignee}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: sm.fg }} />
                <span style={{ fontFamily: fontMono, fontSize: 11, color: sm.fg, letterSpacing: "0.04em" }}>{sm.label}</span>
              </span>
              <span style={{ fontFamily: fontMono, fontSize: 11, color: priMeta[tk.pri], letterSpacing: "0.08em", textTransform: "uppercase" }}>{tk.pri}</span>
              <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted }}>{tk.updated}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Journal ───────────────────────────────────────────────────────────
function JournalTab({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;

  const kindMeta = {
    verdict:  { fg: c.jade,       label: "verdict" },
    commit:   { fg: c.inkSoft,    label: "commit" },
    progress: { fg: c.vermillion, label: "progress" },
    dispatch: { fg: c.ocher,      label: "dispatch" },
    decision: { fg: c.seal,       label: "decision" },
    triage:   { fg: c.inkMuted,   label: "triage" },
    pushback: { fg: c.ocher,      label: "pushback" },
  };

  return (
    <div>
      <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.02em", marginBottom: 12 }}>
        <span style={{ color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase", marginRight: 8 }}>source</span>
        mcp__zenos__journal_read(limit=10) · today · 2026-04-19
      </div>

      <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: "8px 0" }}>
        {JOURNAL.map((e, i) => {
          const km = kindMeta[e.kind];
          return (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "64px 100px 90px 1fr 80px",
              gap: 14, padding: "12px 20px", alignItems: "baseline",
              borderBottom: i < JOURNAL.length - 1 ? `1px solid ${c.inkHair}` : "none",
              fontFamily: fontBody,
            }}>
              <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.04em" }}>{e.t}</span>
              <span style={{ fontFamily: fontMono, fontSize: 11.5, color: c.inkSoft, letterSpacing: "0.02em" }}>@{e.actor}</span>
              <span style={{
                fontFamily: fontMono, fontSize: 10, color: km.fg,
                padding: "2px 7px", border: `1px solid ${km.fg}55`, borderRadius: 2,
                letterSpacing: "0.12em", textTransform: "uppercase",
                justifySelf: "start",
              }}>{km.label}</span>
              <span style={{ fontSize: 12.5, color: c.ink, letterSpacing: "0.02em", lineHeight: 1.6 }}>{e.body}</span>
              <span style={{ fontFamily: fontMono, fontSize: 11, color: c.inkMuted, letterSpacing: "0.04em", justifySelf: "start" }}>{e.task}</span>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 14, display: "flex", gap: 8, alignItems: "center" }}>
        <Btn t={t} variant="ghost"   size="sm" icon={Icons.doc}>load more (limit=20)</Btn>
        <Btn t={t} variant="ghost"   size="sm">filter · actor</Btn>
        <Btn t={t} variant="ghost"   size="sm">filter · kind</Btn>
        <div style={{ flex: 1 }} />
        <Btn t={t} variant="outline" size="sm" icon={Icons.spark}>journal_write</Btn>
      </div>
    </div>
  );
}

window.InkAgentPage = InkAgentPage;
