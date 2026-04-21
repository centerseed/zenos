"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/zen/Toast";
import { updatePreferences } from "@/lib/api";
import { resolveActiveWorkspace } from "@/lib/partner";
import {
  checkCoworkHelperHealth,
  setDefaultHelperBaseUrl,
  setDefaultHelperToken,
} from "@/lib/cowork-helper";

const HELPER_DEFAULT_URL = "http://127.0.0.1:4317";

const MCP_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";

type PlatformId =
  | "claude-code"
  | "claude-cowork"
  | "chatgpt"
  | "codex"
  | "gemini-cli"
  | "antigravity";

type Platform = {
  id: PlatformId;
  name: string;
  useSSE: boolean;
};

const PLATFORMS: Platform[] = [
  { id: "claude-code", name: "Claude Code", useSSE: false },
  { id: "claude-cowork", name: "Claude.ai / Cowork", useSSE: false },
  { id: "chatgpt", name: "ChatGPT", useSSE: false },
  { id: "codex", name: "Codex", useSSE: false },
  { id: "gemini-cli", name: "Gemini CLI", useSSE: true },
  { id: "antigravity", name: "Antigravity", useSSE: true },
];

function getMcpUrl(platform: Platform, apiKey: string): string {
  const endpoint = platform.useSSE ? "sse" : "mcp";
  return `${MCP_BASE}/${endpoint}?api_key=${apiKey}`;
}

function getPrompt(platform: Platform, apiKey: string): string {
  const url = getMcpUrl(platform, apiKey);
  const protocol = platform.useSSE ? "SSE" : "Streamable HTTP";
  return `我要連接 ZenOS MCP server，請完成以下設定：

1. MCP 連線設定
   Server URL: ${url}
   這是 ${protocol} 協議的 MCP server。
   請根據你的平台，把這個 MCP server 加入設定。

2. 安裝治理能力
   連線成功後，請先判斷你目前是 ${platform.name}，再呼叫對應的 setup(platform=...)。
   接著請主動問我要安裝在當前目錄還是家目錄；若我沒特別指定，預設推薦當前目錄。
   如果是首次安裝，先把 zenos-setup 裝進來。

3. 完成正式安裝
   zenos-setup 裝好後，請執行 /zenos-setup 完成正式安裝或後續更新。

4. 安裝完成後說明
   請用很短的方式告訴我 /zenos-setup、/zenos-capture、/zenos-sync、/zenos-governance 分別什麼時候用。`;
}

type SkillGroup = {
  title: string;
  skills: { name: string; desc: string; when: string }[];
};

const SKILL_GROUPS: SkillGroup[] = [
  {
    title: "ZenOS 工作流",
    skills: [
      { name: "/zenos-capture", desc: "建立專案知識庫", when: "首次把專案加入 ZenOS 時" },
      { name: "/zenos-sync", desc: "增量同步", when: "程式碼有變更後，同步到知識庫" },
      { name: "/zenos-governance", desc: "自動治理", when: "讓 AI 自動掃描並修補知識庫" },
    ],
  },
  {
    title: "AI 角色",
    skills: [
      { name: "/architect", desc: "技術規劃", when: "需要架構設計、任務分配時" },
      { name: "/pm", desc: "產品需求", when: "撰寫 Feature Spec 時" },
      { name: "/developer", desc: "功能實作", when: "按照設計實作程式碼時" },
      { name: "/qa", desc: "測試驗收", when: "驗收交付品質時" },
      { name: "/designer", desc: "UI/UX 設計", when: "介面設計決策時" },
      { name: "/debugger", desc: "除錯修復", when: "遇到 bug 需要根因分析時" },
      { name: "/marketing", desc: "內容行銷", when: "撰寫文案、行銷策略時" },
      { name: "/challenger", desc: "挑戰分析", when: "想要多角度審視決策時" },
    ],
  },
  {
    title: "複合流程",
    skills: [
      { name: "/feature", desc: "完整功能開發", when: "從需求到任務的完整流程" },
      { name: "/debug", desc: "協同除錯", when: "多角色一起排查問題" },
      { name: "/triage", desc: "任務盤點", when: "看目前有哪些待辦" },
      { name: "/brainstorm", desc: "系統性腦暴", when: "多角度探索想法" },
    ],
  },
];

const TECHNICAL_PLATFORMS: PlatformId[] = ["claude-code", "codex", "gemini-cli"];

function SetupPage() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const { pushToast } = useToast();
  const [selectedId, setSelectedId] = useState<PlatformId>("claude-code");
  const [showToken, setShowToken] = useState(false);

  // Helper section state
  const [helperToken] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    const stored = window.sessionStorage.getItem("zenos.setup.helperToken");
    if (stored) return stored;
    const token =
      "mk-" + crypto.randomUUID().replace(/-/g, "").slice(0, 12);
    window.sessionStorage.setItem("zenos.setup.helperToken", token);
    return token;
  });
  const [helperConfigured, setHelperConfigured] = useState(false);
  const [helperStatus, setHelperStatus] = useState<
    "idle" | "checking" | "ok" | "error"
  >("idle");

  // Persist platform type when user selects a platform
  const handlePlatformSelect = async (platformId: PlatformId) => {
    setSelectedId(platformId);
    if (!user) return;
    const platformType = TECHNICAL_PLATFORMS.includes(platformId) ? "technical" : "non_technical";
    try {
      const token = await user.getIdToken();
      await updatePreferences(token, { onboarding: { platform_type: platformType, platform_id: platformId } });
    } catch {
      // Non-critical: preference save failure doesn't block setup flow
    }
  };

  const { workspaceRole, isHomeWorkspace } = resolveActiveWorkspace(partner);
  const canManageWorkspace = isHomeWorkspace && workspaceRole === "owner";

  useEffect(() => {
    if (partner && !canManageWorkspace) {
      router.replace("/tasks");
    }
  }, [partner, canManageWorkspace, router]);

  if (!canManageWorkspace) return null;

  const platform = PLATFORMS.find((p) => p.id === selectedId) ?? PLATFORMS[0];
  const apiKey = partner!.apiKey;

  const helperCommand = `cd ~/clients/ZenOS/tools/claude-cowork-helper && \\
ZENOS_API_KEY="${apiKey}" \\
ZENOS_PROJECT="Paceriz" \\
ALLOWED_ORIGINS="https://zenos-naruvia.web.app" \\
LOCAL_HELPER_TOKEN="${helperToken}" \\
ALLOWED_CWDS="$HOME/.zenos/claude-code-helper/workspace" \\
node server.mjs`;

  const handleConfigureHelper = async () => {
    setDefaultHelperBaseUrl(HELPER_DEFAULT_URL);
    setDefaultHelperToken(helperToken);
    setHelperConfigured(true);
    setHelperStatus("checking");
    try {
      const result = await checkCoworkHelperHealth(
        HELPER_DEFAULT_URL,
        helperToken,
      );
      setHelperStatus(result.ok ? "ok" : "error");
    } catch {
      setHelperStatus("error");
    }
  };

  const maskedKey = apiKey.slice(0, 8) + "••••••••";
  const displayKey = showToken ? apiKey : maskedKey;

  const mcpUrl = getMcpUrl(platform, apiKey);
  const displayMcpUrl = getMcpUrl(platform, displayKey);

  const prompt = getPrompt(platform, apiKey);

  const copyText = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    pushToast({
      tone: "success",
      title: `${label} 已複製`,
      description: "可以直接貼到對應位置。",
    });
  };

  return (
    <div className="min-h-screen">
      <main
        id="main-content"
        className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6"
      >
        {/* Section 1 — 選擇平台 */}
        <section className="rounded-[28px] border border-border bg-card p-6">
          <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
            開始安裝
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-foreground">
            選擇你的 AI 工具
          </h1>
          <div className="mt-5 flex flex-wrap gap-2">
            {PLATFORMS.map((p) => {
              const active = p.id === selectedId;
              return (
                <button
                  key={p.id}
                  onClick={() => handlePlatformSelect(p.id)}
                  className={`rounded-full border px-4 py-2 text-sm transition-colors ${
                    active
                      ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100"
                      : "border-border bg-background/70 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {p.name}
                </button>
              );
            })}
          </div>
        </section>

        {/* Section 2 — Step 1: MCP 連結 */}
        <section className="rounded-[28px] border border-border bg-card p-6">
          <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
            Step 1
          </p>
          <h2 className="mt-2 text-xl font-semibold text-foreground">
            複製你的 MCP 連結
          </h2>

          <div className="mt-5 rounded-2xl border border-border bg-[#0f1418] p-4">
            <div className="flex items-start justify-between gap-3">
              <p
                data-testid="mcp-url-display"
                className="break-all font-mono text-sm leading-6 text-slate-100"
              >
                {displayMcpUrl}
              </p>
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => setShowToken((v) => !v)}
                  className="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-500 hover:bg-slate-800"
                >
                  {showToken ? "Hide" : "Show"}
                </button>
                <button
                  onClick={() => copyText(mcpUrl, "MCP 連結")}
                  className="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-500 hover:bg-slate-800"
                >
                  Copy
                </button>
              </div>
            </div>
          </div>

          <p className="mt-3 text-xs text-muted-foreground">
            {platform.useSSE
              ? "此平台使用 SSE 協議 (/sse)。"
              : "此平台使用 Streamable HTTP 協議 (/mcp)。"}
          </p>
        </section>

        {/* Section 3 — Step 2: 貼給 AI 的指令 */}
        <section className="rounded-[28px] border border-border bg-card p-6">
          <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
            Step 2
          </p>
          <h2 className="mt-2 text-xl font-semibold text-foreground">
            複製以下指令，貼到你的 AI 工具
          </h2>

          <div className="mt-5 rounded-2xl border border-border bg-[#0f1418] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                安裝指令
              </p>
              <button
                onClick={() => copyText(prompt, "安裝指令")}
                className="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-500 hover:bg-slate-800"
              >
                Copy
              </button>
            </div>
            <pre
              data-testid="setup-prompt"
              className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-100"
            >
              {prompt}
            </pre>
          </div>
        </section>

        {/* Section — Dashboard AI Helper (optional) */}
        <section className="rounded-[28px] border border-border bg-card p-6">
          <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
            選用
          </p>
          <h2 className="mt-2 text-xl font-semibold text-foreground">
            Dashboard AI 功能
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            讓 Dashboard 的行銷和 CRM 模組直接與 AI 對話。需要 Node.js 和
            Claude Code CLI。如果只用 CLI 不需要安裝。
          </p>

          {/* Step A: 啟動指令 */}
          <div className="mt-5 rounded-2xl border border-border bg-[#0f1418] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                在 Terminal 執行
              </p>
              <button
                onClick={() => copyText(helperCommand, "Helper 啟動指令")}
                className="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-500 hover:bg-slate-800"
              >
                Copy
              </button>
            </div>
            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-100">
              {helperCommand}
            </pre>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            路徑 <code className="text-slate-400">~/clients/ZenOS/tools/claude-cowork-helper</code>{" "}
            可能需要根據你的安裝位置調整。
          </p>

          {/* Step B: 自動設定 Dashboard 連線 */}
          <div className="mt-5 flex items-center gap-3">
            <button
              onClick={handleConfigureHelper}
              className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
            >
              自動設定 Dashboard 連線
            </button>
            {helperConfigured && helperStatus !== "checking" && (
              <span
                className={`text-sm ${
                  helperStatus === "ok"
                    ? "text-emerald-400"
                    : "text-muted-foreground"
                }`}
              >
                {helperStatus === "ok" ? "已設定" : "已設定"}
              </span>
            )}
          </div>

          {/* Step C: 連線狀態 */}
          {helperConfigured && (
            <div className="mt-4 rounded-2xl border border-border bg-background/70 p-4">
              {helperStatus === "checking" && (
                <span className="text-sm text-muted-foreground">
                  正在檢查連線...
                </span>
              )}
              {helperStatus === "ok" && (
                <span className="text-sm text-emerald-400">
                  Helper 已連線
                </span>
              )}
              {helperStatus === "error" && (
                <span className="text-sm text-red-400">
                  無法連線，請確認 Helper 已啟動後重試
                </span>
              )}
            </div>
          )}
        </section>

        {/* Section 4 — Step 3: 安裝完成後的功能 */}
        <section className="rounded-[28px] border border-border bg-card p-6">
          <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
            Step 3
          </p>
          <h2 className="mt-2 text-xl font-semibold text-foreground">
            安裝完成後，你可以使用這些功能
          </h2>

          <div className="mt-6 space-y-8">
            {SKILL_GROUPS.map((group) => (
              <div key={group.title}>
                <p className="mb-3 text-sm font-medium text-foreground">
                  {group.title}
                </p>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {group.skills.map((skill) => (
                    <div
                      key={skill.name}
                      className="rounded-2xl border border-border bg-background/70 p-4"
                    >
                      <p className="font-mono text-sm font-semibold text-emerald-300">
                        {skill.name}
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        {skill.desc}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        使用時機：{skill.when}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 border-t border-border pt-4">
            <Link
              href="/setup/skills"
              className="text-sm text-blue-400 hover:underline"
            >
              查看完整 Skills 說明
            </Link>
          </div>
        </section>

        <div className="flex justify-center">
          <Link
            href="/knowledge-map"
            className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
          >
            前往知識地圖
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>
      </main>
    </div>
  );
}

export default function Page() {
  return <SetupPage />;
}
