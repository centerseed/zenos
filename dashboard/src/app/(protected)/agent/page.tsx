"use client";

// ZenOS · Agent · MCP Settings — Option B (hosted server, read-only)
// Route: /agent
// SPEC: SPEC-zen-ink-real-data.md AC-DATA-MCP-01 to 04

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useInk } from "@/lib/zen-ink/tokens";
import { useToast } from "@/components/zen/Toast";
import { Section } from "@/components/zen/Section";
import { Btn } from "@/components/zen/Btn";
import { Icon, ICONS } from "@/components/zen/Icons";
import {
  AGENT_PLATFORMS as PLATFORMS,
  canCopyAgentConfig,
  getMcpConfig,
  getMcpUrl,
  maskApiKey,
  type AgentPlatformId as PlatformId,
} from "@/lib/agent-config";

// ─── Skills data from design-ref-v2/page_agent.jsx ─────────────────────
type SkillKind = "role" | "governance" | "workflow";

interface Skill {
  name: string;
  ver: string;
  kind: SkillKind;
  owner: string;
  desc: string;
  calls: string[];
}

const SKILLS: Skill[] = [
  // roles
  { name: "architect",        ver: "0.8.0", kind: "role",       owner: "Barry", desc: "系統架構、任務分配、subagent 調度、交付審查。",             calls: ["mcp__zenos__task", "mcp__zenos__confirm", "mcp__zenos__journal_read", "mcp__zenos__plan"] },
  { name: "developer",        ver: "0.4.0", kind: "role",       owner: "Barry", desc: "按 Architect 技術設計實作功能。隔離 context 執行。",         calls: ["Read", "Glob", "Grep", "Write", "Edit", "Bash(cat:*)"] },
  { name: "qa",               ver: "0.4.0", kind: "role",       owner: "Barry", desc: "驗收 Developer 交付，產出 PASS / CONDITIONAL / FAIL。",      calls: ["mcp__zenos__task", "Read", "Glob", "Grep"] },
  { name: "pm",               ver: "0.4.0", kind: "role",       owner: "Barry", desc: "需求整理、里程碑、優先序、backlog 治理。",                   calls: ["mcp__zenos__search", "mcp__zenos__task", "mcp__zenos__plan"] },
  { name: "designer",         ver: "0.2.0", kind: "role",       owner: "Barry", desc: "UI/UX 規劃、設計規格、視覺系統維護。",                       calls: ["mcp__zenos__search", "mcp__zenos__write"] },
  { name: "marketing",        ver: "0.2.0", kind: "role",       owner: "Barry", desc: "情報 / 生成 / 適配 / 發佈的行銷流程。",                       calls: ["mcp__zenos__search", "mcp__zenos__write", "mcp__zenos__analyze"] },
  { name: "challenger",       ver: "0.2.0", kind: "role",       owner: "Barry", desc: "對決策與設計提出反對意見、找出盲點。",                       calls: ["mcp__zenos__search", "mcp__zenos__find_gaps"] },
  { name: "debugger",         ver: "0.1.0", kind: "role",       owner: "Barry", desc: "錯誤根因定位、二分搜尋、最小重現。",                         calls: ["Read", "Grep", "Bash(cat:*)"] },
  // governance skills (zenos-*)
  { name: "zenos-setup",      ver: "2.0.0", kind: "governance", owner: "Barry", desc: "初始化 workspace、skill 同步、版本管理。",                   calls: ["mcp__zenos__setup", "mcp__zenos__list_workspaces"] },
  { name: "zenos-capture",    ver: "2.2.0", kind: "governance", owner: "Barry", desc: "從對話擷取決策 / 設計 / 任務並寫入 SSOT。",                  calls: ["mcp__zenos__write", "mcp__zenos__upload_attachment"] },
  { name: "zenos-sync",       ver: "3.2.0", kind: "governance", owner: "Barry", desc: "本地 skills ↔ SSOT 雙向同步。",                             calls: ["mcp__zenos__batch_update_sources"] },
  { name: "zenos-governance", ver: "2.0.0", kind: "governance", owner: "Barry", desc: "文件 / L2 概念 / 任務治理規則載入器。",                       calls: ["mcp__zenos__governance_guide", "mcp__zenos__suggest_policy"] },
  // workflows
  { name: "feature",          ver: "1.0.0", kind: "workflow",   owner: "Barry", desc: "新功能全流程：PM → Architect → Developer → QA → confirm。", calls: ["architect", "developer", "qa", "pm"] },
  { name: "debug",            ver: "1.0.0", kind: "workflow",   owner: "Barry", desc: "錯誤調查流程：Debugger → Developer → QA。",                  calls: ["debugger", "developer", "qa"] },
  { name: "triage",           ver: "1.0.0", kind: "workflow",   owner: "Barry", desc: "Backlog 分類 / 優先序調整。",                                calls: ["pm", "architect"] },
  { name: "brainstorm",       ver: "1.0.0", kind: "workflow",   owner: "Barry", desc: "多角色腦力激盪：PM + Architect + Challenger。",              calls: ["pm", "architect", "challenger"] },
];

// ─── Zenos MCP tools ────────────────────────────────────────────────────
const ZENOS_TOOLS = [
  { name: "search",               group: "query",    desc: "檢索 entities / tasks / docs。" },
  { name: "get",                  group: "query",    desc: "取單一節點的完整資料。" },
  { name: "analyze",              group: "query",    desc: "關聯 / 影響 / 依賴分析。" },
  { name: "common_neighbors",     group: "query",    desc: "找兩個節點的共同鄰居。" },
  { name: "find_gaps",            group: "query",    desc: "找知識圖譜缺口 / 盲點。" },
  { name: "list_workspaces",      group: "query",    desc: "列出可用 workspaces。" },
  { name: "journal_read",         group: "query",    desc: "讀工作日誌（脈絡恢復）。" },
  { name: "read_source",          group: "query",    desc: "讀取 source（GitHub / Drive / URL）。" },
  { name: "write",                group: "mutation", desc: "寫入 entity / document。" },
  { name: "journal_write",        group: "mutation", desc: "寫工作日誌條目。" },
  { name: "task",                 group: "mutation", desc: "建 / 更新 task（create / update）。" },
  { name: "plan",                 group: "mutation", desc: "建立 / 更新計畫（milestone / goal）。" },
  { name: "batch_update_sources", group: "mutation", desc: "批次更新 source status（valid/stale/broken）。" },
  { name: "upload_attachment",    group: "mutation", desc: "上傳附件並綁到 entity。" },
  { name: "confirm",              group: "gate",     desc: "Architect 最終驗收（accepted=True → done）。" },
  { name: "setup",                group: "admin",    desc: "workspace 初始化。" },
  { name: "governance_guide",     group: "admin",    desc: "回傳治理文件摘要（寫文件 / L2 / 任務前必讀）。" },
  { name: "suggest_policy",       group: "admin",    desc: "針對 workspace 建議治理策略。" },
];

type HealthStatus = "checking" | "connected" | "error" | "idle";
type TabKey = "cli" | "mcp" | "skills";

// ─── Page ───────────────────────────────────────────────────────────────
export default function AgentPage() {
  const { partner } = useAuth();
  const t = useInk("light");
  const { c, fontHead, fontBody, fontMono } = t;
  const { pushToast } = useToast();

  const [tab, setTab] = useState<TabKey>("cli");

  // MCP health check state
  const [healthStatus, setHealthStatus] = useState<HealthStatus>("idle");
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const apiKey = partner?.apiKey ?? "";
  const canCopy = canCopyAgentConfig(apiKey);

  // Run health check on mount once apiKey is available
  useEffect(() => {
    if (!apiKey) return;
    runHealthCheck();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  function runHealthCheck() {
    if (!apiKey) return;
    setHealthStatus("checking");
    setLatencyMs(null);
    const start = Date.now();
    const url = getMcpUrl({ useSSE: false }, apiKey);
    fetch(url, { method: "GET", signal: AbortSignal.timeout(8000) })
      .then((res) => {
        const ms = Date.now() - start;
        setLatencyMs(ms);
        setHealthStatus(res.ok || res.status === 405 ? "connected" : "error");
      })
      .catch(() => {
        setHealthStatus("error");
        setLatencyMs(null);
      });
  }

  const maskedKey = apiKey ? maskApiKey(apiKey) : "————";
  const displayKey = showKey ? apiKey : maskedKey;

  const httpPlatform = PLATFORMS[0]; // claude-code, http
  const configUrl = getMcpUrl(httpPlatform, apiKey);
  const displayConfigUrl = getMcpUrl(httpPlatform, displayKey);

  async function copyConfig(platformId: PlatformId) {
    if (!canCopy) return;
    const platform = PLATFORMS.find((p) => p.id === platformId) ?? PLATFORMS[0];
    const json = getMcpConfig(platform, apiKey);
    await navigator.clipboard.writeText(json);
    pushToast({
      tone: "success",
      title: `已複製 ${platform.name} 設定`,
      description: "可直接貼到 mcp.json 或對應設定欄位。",
    });
  }

  // The single hosted server JSON preview
  const jsonPreview = getMcpConfig(httpPlatform, apiKey);

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section
        t={t}
        eyebrow="AGENT · 安裝與設定"
          title="Agent · MCP"
          en="Setup"
        subtitle="這是進階參考頁：看 hosted MCP、skills 與本地 helper 的結構。第一次接入請優先用 /setup 或 /settings。"
      />

      {/* KPI strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 1,
          background: c.inkHair,
          border: `1px solid ${c.inkHair}`,
          marginBottom: 24,
        }}
      >
        {[
          {
            k: "LOCAL HELPER",
            v: "—",
            sub: "僅 Claude Code CLI 本地偵測",
          },
          {
            k: "MCP SERVERS",
            v: "1",
            sub: "ZenOS · hosted",
          },
          {
            k: "SKILLS · manifest",
            v: "—",
            sub: "本地管理",
          },
        ].map((s, i) => (
          <div
            key={i}
            style={{ background: c.surface, padding: "16px 18px" }}
          >
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              {s.k}
            </div>
            <div
              style={{
                fontFamily: fontHead,
                fontSize: 28,
                fontWeight: 500,
                color: c.ink,
                letterSpacing: "0.02em",
              }}
            >
              {s.v}
            </div>
            <div
              style={{
                fontSize: 11,
                color: c.inkMuted,
                marginTop: 2,
                fontFamily: fontMono,
                letterSpacing: "0.02em",
              }}
            >
              {s.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 20,
          borderBottom: `1px solid ${c.inkHair}`,
          overflowX: "auto",
        }}
      >
        {(
          [
            ["cli",    "Local helper", "claude CLI",        null],
            ["mcp",    "MCP",          ".claude/mcp.json",  1],
            ["skills", "Agents & Skills", ".claude/skills", SKILLS.length],
          ] as [TabKey, string, string, number | null][]
        ).map(([k, label, sub, n]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: "none",
              borderBottom:
                tab === k
                  ? `2px solid ${c.vermillion}`
                  : "2px solid transparent",
              marginBottom: -1,
              cursor: "pointer",
              color: tab === k ? c.ink : c.inkMuted,
              display: "flex",
              alignItems: "center",
              gap: 8,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <div style={{ textAlign: "left" }}>
              <div
                style={{
                  fontFamily: fontHead,
                  fontSize: 13,
                  letterSpacing: "0.04em",
                  fontWeight: tab === k ? 600 : 500,
                }}
              >
                {label}
              </div>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 9,
                  color: c.inkFaint,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  marginTop: 1,
                }}
              >
                {sub}
              </div>
            </div>
            {n != null && (
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  padding: "1px 6px",
                  background: c.surface,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: 2,
                }}
              >
                {n}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "cli" && (
        <LocalHelperTab
          t={t}
          fontHead={fontHead}
          fontBody={fontBody}
          fontMono={fontMono}
          c={c}
        />
      )}
      {tab === "mcp" && (
        <MCPTab
          t={t}
          fontHead={fontHead}
          fontBody={fontBody}
          fontMono={fontMono}
          c={c}
          apiKey={apiKey}
          canCopy={canCopy}
          healthStatus={healthStatus}
          latencyMs={latencyMs}
          showJson={showJson}
          setShowJson={setShowJson}
          showKey={showKey}
          setShowKey={setShowKey}
          displayConfigUrl={displayConfigUrl}
          jsonPreview={jsonPreview}
          onCopyConfig={copyConfig}
          onRefreshHealth={runHealthCheck}
        />
      )}
      {tab === "skills" && (
        <SkillsTab
          t={t}
          fontHead={fontHead}
          fontBody={fontBody}
          fontMono={fontMono}
          c={c}
        />
      )}
    </div>
  );
}

// ─── Local Helper Tab ───────────────────────────────────────────────────
function LocalHelperTab({
  fontHead,
  fontBody,
  fontMono,
  c,
}: {
  t: ReturnType<typeof useInk>;
  fontHead: string;
  fontBody: string;
  fontMono: string;
  c: ReturnType<typeof useInk>["c"];
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr",
        gap: 18,
        maxWidth: 1040,
      }}
    >
      {/* Info banner */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <Icon d={ICONS.spark} size={16} style={{ color: c.ocher, flexShrink: 0 }} />
        <span
          style={{
            fontFamily: fontBody,
            fontSize: 12.5,
            color: c.inkMuted,
            lineHeight: 1.6,
          }}
        >
          Dashboard 無法偵測本地狀態，請至 Claude Code CLI 操作。本頁僅供安裝參考。
        </span>
      </div>

      {/* Status card */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 2,
            background: c.paperWarm,
            border: `1px solid ${c.inkHair}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: fontMono,
            fontSize: 14,
            color: c.vermillion,
            fontWeight: 600,
            letterSpacing: "0.04em",
          }}
        >
          CC
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: fontHead,
              fontSize: 16,
              fontWeight: 500,
              color: c.ink,
              letterSpacing: "0.04em",
            }}
          >
            Claude Code CLI
          </div>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 11,
              color: c.inkMuted,
              letterSpacing: "0.02em",
              marginTop: 3,
            }}
          >
            本地 agent 執行代理。共用 .claude/ 設定、mcp.json。
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: c.inkFaint,
            }}
          />
          <span
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
            }}
          >
            —
          </span>
        </div>
      </div>

      {/* Install section */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
        }}
      >
        <HdrBlock
          fontHead={fontHead}
          fontMono={fontMono}
          c={c}
          title="安裝 · Binary"
          en="Installation"
        >
          若尚未安裝 Claude Code CLI，執行以下指令。
        </HdrBlock>

        {/* state fields */}
        <div
          style={{
            padding: "16px 22px",
            borderBottom: `1px solid ${c.inkHair}`,
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 16,
          }}
        >
          {[
            { k: "binary path", v: "—" },
            { k: "version",     v: "—" },
            { k: "last check",  v: "—" },
          ].map((x) => (
            <div key={x.k}>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 9,
                  color: c.inkFaint,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  marginBottom: 5,
                }}
              >
                {x.k}
              </div>
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 12.5,
                  color: c.inkFaint,
                }}
              >
                {x.v}
              </div>
            </div>
          ))}
        </div>

        <div style={{ padding: "14px 22px" }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 9,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            install · curl
          </div>
          <pre
            style={{
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              borderRadius: 2,
              padding: "12px 14px",
              margin: 0,
              fontFamily: fontMono,
              fontSize: 11.5,
              color: c.ink,
              letterSpacing: "0.02em",
              lineHeight: 1.7,
              overflow: "auto",
            }}
          >
            <span style={{ color: c.inkFaint }}>$ </span>
            {"curl -fsSL https://claude.ai/install.sh | sh\n"}
            <span style={{ color: c.inkFaint }}>$ </span>
            {"claude --version"}
          </pre>

          <div
            style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}
          >
            <button
              disabled
              style={{
                padding: "4px 10px",
                fontSize: 11,
                fontFamily: fontBody,
                fontWeight: 500,
                background: "transparent",
                color: c.inkFaint,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                cursor: "not-allowed",
                opacity: 0.5,
              }}
            >
              檢查更新 —
            </button>
            <button
              disabled
              style={{
                padding: "4px 10px",
                fontSize: 11,
                fontFamily: fontBody,
                fontWeight: 500,
                background: "transparent",
                color: c.inkFaint,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                cursor: "not-allowed",
                opacity: 0.5,
              }}
            >
              重新偵測路徑 —
            </button>
            <div style={{ flex: 1 }} />
            <a
              href="https://docs.anthropic.com/claude/reference/claude-code"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: "4px 10px",
                fontSize: 11,
                fontFamily: fontBody,
                fontWeight: 500,
                background: "transparent",
                color: c.inkMuted,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                cursor: "pointer",
                textDecoration: "none",
              }}
            >
              打開官方文件
            </a>
          </div>
        </div>
      </div>

      {/* Project binding */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
        }}
      >
        <HdrBlock
          fontHead={fontHead}
          fontMono={fontMono}
          c={c}
          title="專案綁定 · Project"
          en="Project binding"
        >
          啟動時的 workspace 目錄決定 .claude/ 讀哪份設定。本機狀態無法從 Dashboard 偵測。
        </HdrBlock>
        <div style={{ padding: "14px 22px 16px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 8,
              padding: "10px 14px",
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              borderRadius: 2,
            }}
          >
            {[
              { k: ".claude/mcp.json" },
              { k: ".claude/settings.json" },
              { k: ".claude/skills/manifest" },
            ].map((x) => (
              <div
                key={x.k}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: c.inkFaint,
                  }}
                />
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 11,
                    color: c.inkMuted,
                    letterSpacing: "0.02em",
                  }}
                >
                  {x.k}
                </span>
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                  }}
                >
                  —
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Runtime toggles — disabled */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
        }}
      >
        <HdrBlock
          fontHead={fontHead}
          fontMono={fontMono}
          c={c}
          title="執行模式 · Runtime"
          en="Runtime"
        >
          執行模式由本地 CLI 管理，Dashboard 不可修改。
        </HdrBlock>
        {[
          { l: "常駐 daemon（推薦）",           hint: "開啟後 UI 呼叫透過 unix socket，延遲 < 20ms。" },
          { l: "自動讀 .claude/ 設定",          hint: "helper 啟動時載入 skills / mcp / allowedTools。" },
          { l: "使用專案的 mcp.json",           hint: "關閉後改用 global helper 設定（~/.claude/mcp.json）。" },
          { l: "允許 Bash 執行（非白名單）",     hint: "開啟後 agent 可跑任意 shell 指令；謹慎使用。" },
        ].map((r, i, arr) => (
          <div
            key={r.l}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto",
              gap: 20,
              padding: "14px 22px",
              alignItems: "center",
              borderBottom:
                i < arr.length - 1 ? `1px solid ${c.inkHair}` : "none",
              opacity: 0.5,
            }}
          >
            <div>
              <div
                style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}
              >
                {r.l}
              </div>
              <div
                style={{
                  fontSize: 11.5,
                  color: c.inkMuted,
                  marginTop: 3,
                  lineHeight: 1.6,
                }}
              >
                {r.hint}
              </div>
            </div>
            <span
              style={{
                fontFamily: fontMono,
                fontSize: 11,
                color: c.inkFaint,
                letterSpacing: "0.08em",
              }}
            >
              —
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MCP Tab ─────────────────────────────────────────────────────────────
function MCPTab({
  t,
  fontHead,
  fontBody,
  fontMono,
  c,
  apiKey,
  canCopy,
  healthStatus,
  latencyMs,
  showJson,
  setShowJson,
  showKey,
  setShowKey,
  displayConfigUrl,
  jsonPreview,
  onCopyConfig,
  onRefreshHealth,
}: {
  t: ReturnType<typeof useInk>;
  fontHead: string;
  fontBody: string;
  fontMono: string;
  c: ReturnType<typeof useInk>["c"];
  apiKey: string;
  canCopy: boolean;
  healthStatus: HealthStatus;
  latencyMs: number | null;
  showJson: boolean;
  setShowJson: (v: boolean) => void;
  showKey: boolean;
  setShowKey: (v: boolean) => void;
  displayConfigUrl: string;
  jsonPreview: string;
  onCopyConfig: (p: PlatformId) => void;
  onRefreshHealth: () => void;
}) {
  const healthDot =
    healthStatus === "connected"
      ? c.jade
      : healthStatus === "error"
      ? c.vermillion
      : c.inkFaint;
  const healthLabel =
    healthStatus === "checking"
      ? "checking…"
      : healthStatus === "connected"
      ? "connected"
      : healthStatus === "error"
      ? "error"
      : "—";

  return (
    <div>
      {/* toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 11,
            color: c.inkMuted,
            letterSpacing: "0.04em",
          }}
        >
          <span
            style={{
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              marginRight: 8,
            }}
          >
            source
          </span>
          hosted · ZenOS Cloud
        </div>
        <div style={{ flex: 1 }} />
        <Btn
          t={t}
          variant="ghost"
          size="sm"
          icon={ICONS.doc}
          onClick={() => setShowJson(!showJson)}
        >
          {showJson ? "hide JSON" : "show JSON"}
        </Btn>
        <Btn
          t={t}
          variant="ghost"
          size="sm"
          icon={ICONS.spark}
          onClick={onRefreshHealth}
        >
          refresh
        </Btn>
      </div>

      {/* JSON preview */}
      {showJson && (
        <pre
          style={{
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            padding: "14px 18px",
            marginBottom: 14,
            fontFamily: fontMono,
            fontSize: 11.5,
            color: c.inkSoft,
            letterSpacing: "0.02em",
            lineHeight: 1.6,
            overflow: "auto",
          }}
        >
          {jsonPreview}
        </pre>
      )}

      {/* Server card */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          overflow: "hidden",
          maxWidth: 680,
        }}
      >
        {/* header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: `1px solid ${c.inkHairBold}`,
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
          }}
        >
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 2,
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: fontMono,
              fontSize: 11,
              color: c.vermillion,
              fontWeight: 600,
              letterSpacing: "0.08em",
            }}
          >
            HTTP
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 15,
                color: c.ink,
                fontWeight: 500,
                letterSpacing: "0.02em",
              }}
            >
              zenos
            </div>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                marginTop: 3,
              }}
            >
              MCP server · http
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: healthDot,
                boxShadow:
                  healthStatus === "connected"
                    ? `0 0 0 3px ${c.jade}22`
                    : "none",
              }}
            />
            <span
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: healthDot,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
              }}
            >
              {healthLabel}
            </span>
          </div>
        </div>

        {/* config */}
        <div
          style={{
            padding: "12px 18px",
            borderBottom: `1px solid ${c.inkHair}`,
            background: c.paperWarm,
          }}
        >
          <ConfigRow
            fontMono={fontMono}
            c={c}
            label="url"
            value={displayConfigUrl}
          />
          <div style={{ marginTop: 8, display: "flex", gap: 6, alignItems: "center" }}>
            <button
              onClick={() => setShowKey(!showKey)}
              style={{
                padding: "3px 10px",
                fontSize: 10,
                fontFamily: fontMono,
                background: "transparent",
                color: c.inkMuted,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                cursor: "pointer",
                letterSpacing: "0.04em",
              }}
            >
              {showKey ? "hide key" : "show key"}
            </button>
          </div>
          <ConfigRow
            fontMono={fontMono}
            c={c}
            label="type"
            value="http"
          />
          <ConfigRow
            fontMono={fontMono}
            c={c}
            label="transport"
            value="Streamable HTTP"
          />
          <ConfigRow
            fontMono={fontMono}
            c={c}
            label="tools exposed"
            value={String(ZENOS_TOOLS.length)}
          />
          <ConfigRow
            fontMono={fontMono}
            c={c}
            label="latency p50"
            value={latencyMs != null ? `${latencyMs}ms` : "—"}
          />
        </div>

        {/* Copy config row */}
        <div
          style={{
            padding: "12px 18px",
            borderBottom: `1px solid ${c.inkHair}`,
          }}
        >
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 9,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            複製設定到…
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {PLATFORMS.map((p) => (
              <button
                key={p.id}
                onClick={() => onCopyConfig(p.id)}
                disabled={!canCopy}
                style={{
                  padding: "5px 12px",
                  fontSize: 11,
                  fontFamily: fontBody,
                  fontWeight: 500,
                  background: c.paperWarm,
                  color: c.inkMuted,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: 2,
                  cursor: canCopy ? "pointer" : "not-allowed",
                  letterSpacing: "0.02em",
                  transition: "all .12s",
                  opacity: canCopy ? 1 : 0.5,
                }}
                onMouseEnter={(e) => {
                  if (!canCopy) return;
                  e.currentTarget.style.background = c.surface;
                  e.currentTarget.style.color = c.ink;
                  e.currentTarget.style.borderColor = c.inkHairBold;
                }}
                onMouseLeave={(e) => {
                  if (!canCopy) return;
                  e.currentTarget.style.background = c.paperWarm;
                  e.currentTarget.style.color = c.inkMuted;
                  e.currentTarget.style.borderColor = c.inkHair;
                }}
              >
                {p.name}
              </button>
            ))}
          </div>
          {!canCopy && (
            <div
              style={{
                marginTop: 10,
                fontFamily: fontBody,
                fontSize: 12,
                color: c.ocher,
                lineHeight: 1.6,
              }}
            >
              API key 尚未取得，暫時不能複製可直接使用的 MCP 設定。
            </div>
          )}
        </div>

        {/* Tools list */}
        <div style={{ padding: "12px 18px" }}>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 9,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            exposed tools ({ZENOS_TOOLS.length})
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 4,
            }}
          >
            {ZENOS_TOOLS.map((tool) => (
              <div
                key={tool.name}
                style={{
                  fontFamily: fontMono,
                  fontSize: 11,
                  color: c.inkSoft,
                  padding: "3px 8px",
                  background: c.paperWarm,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: 2,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span
                  style={{
                    color:
                      tool.group === "query"
                        ? c.jade
                        : tool.group === "mutation"
                        ? c.ocher
                        : tool.group === "gate"
                        ? c.vermillion
                        : c.inkFaint,
                  }}
                >
                  ›
                </span>
                <span style={{ letterSpacing: "0.02em" }}>{tool.name}</span>
              </div>
            ))}
          </div>
          <div
            style={{
              marginTop: 8,
              fontFamily: fontMono,
              fontSize: 9,
              color: c.inkFaint,
              letterSpacing: "0.12em",
            }}
          >
            jade = query · ocher = mutation · vermillion = gate · faint = admin
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Skills Tab ──────────────────────────────────────────────────────────
function SkillsTab({
  fontHead,
  fontBody,
  fontMono,
  c,
}: {
  t: ReturnType<typeof useInk>;
  fontHead: string;
  fontBody: string;
  fontMono: string;
  c: ReturnType<typeof useInk>["c"];
}) {
  const [sel, setSel] = useState<string>("architect");
  const [kind, setKind] = useState<string>("all");

  const filtered =
    kind === "all" ? SKILLS : SKILLS.filter((s) => s.kind === kind);
  const active = SKILLS.find((s) => s.name === sel) ?? SKILLS[0];

  const kindMeta: Record<
    SkillKind,
    { fg: string; bg: string; label: string }
  > = {
    role:       { fg: c.vermillion, bg: c.vermSoft, label: "role" },
    governance: { fg: c.ocher,      bg: c.surface,  label: "governance" },
    workflow:   { fg: c.jade,       bg: c.surface,  label: "workflow" },
  };

  return (
    <div>
      {/* Info banner */}
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          padding: "12px 18px",
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <Icon d={ICONS.spark} size={14} style={{ color: c.ocher, flexShrink: 0 }} />
        <span
          style={{
            fontFamily: fontBody,
            fontSize: 12,
            color: c.inkMuted,
            lineHeight: 1.6,
          }}
        >
          本地 agent skills 由 Claude Code CLI 管理。此清單僅為參考。runs / version 等本地狀態無法從 Dashboard 讀取，顯示為 —。
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 440px",
          gap: 20,
        }}
      >
        {/* List */}
        <div>
          <div
            style={{
              display: "flex",
              gap: 10,
              marginBottom: 12,
              alignItems: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                padding: 2,
              }}
            >
              {(
                [
                  ["all",        "all"],
                  ["role",       "role"],
                  ["governance", "governance"],
                  ["workflow",   "workflow"],
                ] as [string, string][]
              ).map(([k, l]) => (
                <button
                  key={k}
                  onClick={() => setKind(k)}
                  style={{
                    padding: "5px 12px",
                    background: kind === k ? c.ink : "transparent",
                    color: kind === k ? c.paper : c.inkMuted,
                    border: "none",
                    borderRadius: 2,
                    cursor: "pointer",
                    fontSize: 11,
                    fontFamily: fontMono,
                    letterSpacing: "0.06em",
                  }}
                >
                  {l}
                </button>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <span
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
              }}
            >
              publisher · ZenOS Platform · owner · Barry
            </span>
          </div>

          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              borderRadius: 2,
            }}
          >
            {/* table header */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "28px 1fr 110px 80px 80px",
                gap: 10,
                padding: "10px 16px",
                borderBottom: `1px solid ${c.inkHairBold}`,
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
              }}
            >
              <span />
              <span>SKILL · description</span>
              <span>KIND</span>
              <span>VERSION</span>
              <span>RUNS · 7d</span>
            </div>

            {filtered.map((s, i) => {
              const isSel = s.name === sel;
              const km = kindMeta[s.kind];
              return (
                <button
                  key={s.name}
                  onClick={() => setSel(s.name)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "28px 1fr 110px 80px 80px",
                    gap: 10,
                    alignItems: "center",
                    width: "100%",
                    padding: "12px 16px",
                    background: isSel ? c.paperWarm : "transparent",
                    border: "none",
                    borderLeft: isSel
                      ? `2px solid ${c.vermillion}`
                      : "2px solid transparent",
                    borderBottom:
                      i < filtered.length - 1
                        ? `1px solid ${c.inkHair}`
                        : "none",
                    cursor: "pointer",
                    textAlign: "left",
                    fontFamily: fontBody,
                  }}
                >
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 14,
                      color: km.fg,
                    }}
                  >
                    ·
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontFamily: fontMono,
                        fontSize: 13,
                        color: c.ink,
                        letterSpacing: "0.02em",
                        fontWeight: 500,
                      }}
                    >
                      {s.name}
                    </div>
                    <div
                      style={{
                        fontSize: 11.5,
                        color: c.inkMuted,
                        marginTop: 3,
                        letterSpacing: "0.01em",
                      }}
                    >
                      {s.desc}
                    </div>
                  </div>
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: km.fg,
                      padding: "2px 8px",
                      background: km.bg,
                      border: `1px solid ${km.fg}44`,
                      borderRadius: 2,
                      textTransform: "uppercase",
                      letterSpacing: "0.12em",
                      justifySelf: "start",
                    }}
                  >
                    {km.label}
                  </span>
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 11,
                      color: c.inkFaint,
                    }}
                  >
                    —
                  </span>
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 11,
                      color: c.inkFaint,
                    }}
                  >
                    —
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail */}
        <aside
          style={{
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            alignSelf: "flex-start",
            position: "sticky",
            top: 20,
          }}
        >
          <div
            style={{
              padding: "16px 20px 12px",
              borderBottom: `1px solid ${c.inkHair}`,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: kindMeta[active.kind].fg,
                  padding: "2px 7px",
                  background: kindMeta[active.kind].bg,
                  border: `1px solid ${kindMeta[active.kind].fg}44`,
                  borderRadius: 2,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                }}
              >
                {active.kind}
              </span>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.12em",
                }}
              >
                v— · {active.owner}
              </span>
            </div>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 18,
                color: c.ink,
                letterSpacing: "0.02em",
                fontWeight: 500,
              }}
            >
              {active.name}
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: c.inkSoft,
                lineHeight: 1.7,
                marginTop: 8,
              }}
            >
              {active.desc}
            </div>
          </div>

          <div
            style={{
              padding: "14px 20px",
              borderBottom: `1px solid ${c.inkHair}`,
            }}
          >
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 9,
                color: c.inkFaint,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              {active.kind === "workflow" ? "invokes" : "allowed calls"}
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              {active.calls.map((tool) => (
                <div
                  key={tool}
                  style={{
                    fontFamily: fontMono,
                    fontSize: 11.5,
                    color: c.ink,
                    padding: "4px 10px",
                    background: c.paperWarm,
                    border: `1px solid ${c.inkHair}`,
                    borderRadius: 2,
                    letterSpacing: "0.02em",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <span style={{ color: c.vermillion }}>›</span>
                  <span>{tool}</span>
                </div>
              ))}
            </div>
          </div>

          <div
            style={{
              padding: "14px 20px",
              borderBottom: `1px solid ${c.inkHair}`,
            }}
          >
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 9,
                color: c.inkFaint,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              path
            </div>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 11.5,
                color: c.inkSoft,
                letterSpacing: "0.02em",
              }}
            >
              .claude/skills/{active.name}/SKILL.md
            </div>
          </div>

          <div style={{ padding: "12px 20px" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
              }}
            >
              {[
                { k: "runs 7d", v: "—" },
                { k: "version", v: "—" },
              ].map((x) => (
                <div key={x.k}>
                  <div
                    style={{
                      fontFamily: fontMono,
                      fontSize: 9,
                      color: c.inkFaint,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      marginBottom: 3,
                    }}
                  >
                    {x.k}
                  </div>
                  <div
                    style={{
                      fontFamily: fontMono,
                      fontSize: 13,
                      color: c.inkFaint,
                    }}
                  >
                    {x.v}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

// ─── Shared helpers ───────────────────────────────────────────────────────
function HdrBlock({
  fontHead,
  fontMono,
  c,
  title,
  en,
  children,
}: {
  fontHead: string;
  fontMono: string;
  c: ReturnType<typeof useInk>["c"];
  title: string;
  en: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        padding: "16px 22px",
        borderBottom: `1px solid ${c.inkHair}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 12,
        }}
      >
        <div
          style={{
            fontFamily: fontHead,
            fontSize: 16,
            fontWeight: 500,
            color: c.ink,
            letterSpacing: "0.04em",
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
          }}
        >
          {en}
        </div>
      </div>
      <div
        style={{
          fontSize: 12,
          color: c.inkMuted,
          marginTop: 4,
          lineHeight: 1.6,
        }}
      >
        {children}
      </div>
    </div>
  );
}

function ConfigRow({
  fontMono,
  c,
  label,
  value,
}: {
  fontMono: string;
  c: ReturnType<typeof useInk>["c"];
  label: string;
  value: string;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "100px 1fr",
        gap: 8,
        padding: "4px 0",
        fontFamily: fontMono,
        fontSize: 11,
      }}
    >
      <span
        style={{
          color: c.inkFaint,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span
        style={{
          color: c.inkSoft,
          letterSpacing: "0.02em",
          wordBreak: "break-all",
        }}
      >
        {value}
      </span>
    </div>
  );
}
