"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppNav } from "@/components/AppNav";
import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/toast";
import { resolveActiveWorkspace } from "@/lib/partner";

const MCP_SERVER_URL = "https://zenos-mcp-165893875709.asia-east1.run.app";
const STREAMABLE_HTTP_URL = `${MCP_SERVER_URL}/mcp`;

type PlatformId =
  | "claude-code"
  | "claude-cowork"
  | "chatgpt"
  | "codex"
  | "gemini-cli"
  | "antigravity";

type PlatformInstall = {
  id: PlatformId;
  name: string;
  badge: string;
  configPath: string;
  mcpMode: string;
  setupPlatform: "claude_code" | "claude_web" | "codex";
  installSteps: string[];
  setupSummary: string[];
  ontologyStart: string[];
  notes?: string[];
  sources: { label: string; href: string }[];
  configExample: (apiKey: string) => string;
};

const PLATFORM_INSTALLS: PlatformInstall[] = [
  {
    id: "claude-code",
    name: "Claude Code",
    badge: "Project file",
    configPath: ".claude/mcp.json",
    mcpMode: "Streamable HTTP + Bearer token",
    setupPlatform: "claude_code",
    installSteps: [
      "在專案內建立或更新 `.claude/mcp.json`。",
      "加入 `zenos` MCP server，指向 ZenOS remote MCP URL。",
      "把 API key 放在 Authorization Bearer header。",
      "重開 Claude Code，確認 server 被發現。",
    ],
    setupSummary: [
      "執行 `setup(platform=\"claude_code\")`。",
      "套用 workflow skills、slash commands、CLAUDE.md addition。",
      "驗證 `search(collection=\"entities\", entity_level=\"L1\")` 可用。",
    ],
    ontologyStart: [
      "既有 repo 第一次上線：先 `zenos-capture <repo_path>`。",
      "建立初始 ontology 後，再交給 `zenos-sync` 做增量同步。",
    ],
    sources: [
      {
        label: "Anthropic Claude Code overview",
        href: "https://docs.anthropic.com/en/docs/claude-code/overview",
      },
    ],
    configExample: (apiKey) =>
      JSON.stringify(
        {
          mcpServers: {
            zenos: {
              type: "http",
              url: STREAMABLE_HTTP_URL,
              headers: {
                Authorization: `Bearer ${apiKey}`,
              },
            },
          },
        },
        null,
        2
      ),
  },
  {
    id: "claude-cowork",
    name: "Claude / Cowork",
    badge: "Cloud connector",
    configPath: "Customize > Connectors",
    mcpMode: "Remote connector URL",
    setupPlatform: "claude_web",
    installSteps: [
      "進入 `Customize > Connectors`。",
      "按 `+` 並選 `Add custom connector`。",
      "填入 `zenos` 名稱與 ZenOS remote MCP URL。",
      "完成 connector auth，並在對話中啟用。",
    ],
    setupSummary: [
      "執行 `setup(platform=\"claude_web\")`。",
      "把回傳的 Project Instructions 貼進專案設定。",
      "需要時再補上 governance 文件作為 project docs。",
    ],
    ontologyStart: [
      "第一次幫既有專案建庫時，用 `zenos-capture` workflow 啟動。",
      "平常維護則以 `zenos-sync` 和治理回圈為主。",
    ],
    notes: [
      "Anthropic 的 custom connectors 文件目前標示為 beta。",
      "Remote MCP 需要 Anthropic 雲端可以連到，不適合只在本機可見的 server。",
    ],
    sources: [
      {
        label: "Claude custom connectors help",
        href: "https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities",
      },
    ],
    configExample: (apiKey) => `${STREAMABLE_HTTP_URL}?api_key=${apiKey}`,
  },
  {
    id: "chatgpt",
    name: "ChatGPT",
    badge: "Developer mode",
    configPath: "Settings > Apps > Advanced settings",
    mcpMode: "Remote MCP app",
    setupPlatform: "codex",
    installSteps: [
      "先在 ChatGPT web 開啟 Developer mode。",
      "到 Apps settings 按 `Create app`。",
      "把 ZenOS remote MCP server 設成 app backend。",
      "在 Developer mode 對話中啟用這個 app。",
    ],
    setupSummary: [
      "目前可沿用 `setup(platform=\"codex\")` 的精簡安裝說明作為 ChatGPT agent instructions。",
      "頁面上應明示：ChatGPT 沒有 repo-level skill 檔案，主要靠 app + instructions。",
    ],
    ontologyStart: [
      "想讓 ChatGPT 接手既有專案 onboarding，先確認 MCP app 真的能查到 ZenOS。",
      "再以 capture 流程做第一次建庫，不要直接進 sync。",
    ],
    notes: [
      "OpenAI 的 Developer mode 文件目前標示為 beta，且有方案限制。",
    ],
    sources: [
      {
        label: "OpenAI ChatGPT Developer mode",
        href: "https://developers.openai.com/api/docs/guides/developer-mode",
      },
    ],
    configExample: (apiKey) => `${STREAMABLE_HTTP_URL}?api_key=${apiKey}`,
  },
  {
    id: "codex",
    name: "Codex",
    badge: "Local config",
    configPath: "~/.codex/config.toml or .codex/config.toml",
    mcpMode: "Streamable HTTP + Bearer token",
    setupPlatform: "codex",
    installSteps: [
      "編輯 `~/.codex/config.toml` 或專案內 `.codex/config.toml`。",
      "加入 `zenos` MCP server 指向 remote endpoint。",
      "填入 Bearer token。",
      "重開 Codex CLI 或 reload workspace。",
    ],
    setupSummary: [
      "執行 `setup(platform=\"codex\")`。",
      "把 AGENTS.md addition 放進 repo 指令檔。",
      "必要時再下載 ZenOS skills bundle 作為本地治理說明。",
    ],
    ontologyStart: [
      "對既有 repo，第一次先 capture，再 sync。",
      "若要全自動治理，再進 `zenos-governance`。",
    ],
    sources: [
      {
        label: "OpenAI Codex MCP docs",
        href: "https://developers.openai.com/codex/mcp",
      },
    ],
    configExample: (apiKey) => `[mcp_servers.zenos]
transport = "http"
url = "${STREAMABLE_HTTP_URL}"
bearer_token = "${apiKey}"`,
  },
  {
    id: "gemini-cli",
    name: "Gemini CLI",
    badge: "CLI settings",
    configPath: "settings.json",
    mcpMode: "SSE / Streamable HTTP",
    setupPlatform: "codex",
    installSteps: [
      "編輯 Gemini CLI `settings.json`，或用 `gemini mcp add` 管理。",
      "在 `mcpServers` 下加入 `zenos`。",
      "設定 remote URL 與 Authorization header。",
      "開新 session 後確認 server 可見。",
    ],
    setupSummary: [
      "ZenOS 還沒有 Gemini 專屬 setup adapter，頁面上可先引導使用 codex-style instructions。",
      "重點是讓 agent 能讀到治理規則，再透過 MCP 操作 ZenOS。",
    ],
    ontologyStart: [
      "Gemini 接既有專案時，一樣先 capture 建庫。",
      "之後用 sync 跟上 git 變更。",
    ],
    notes: [
      "Gemini CLI 文件顯示 MCP discovery 來自 `settings.json`，並支援 SSE 與 Streamable HTTP。",
    ],
    sources: [
      {
        label: "Gemini CLI MCP guide",
        href: "https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md",
      },
    ],
    configExample: (apiKey) =>
      JSON.stringify(
        {
          mcpServers: {
            zenos: {
              httpUrl: STREAMABLE_HTTP_URL,
              headers: {
                Authorization: `Bearer ${apiKey}`,
              },
            },
          },
        },
        null,
        2
      ),
  },
  {
    id: "antigravity",
    name: "Antigravity",
    badge: "CLI or repo file",
    configPath: "antigravity CLI or .vscode/mcp.json",
    mcpMode: "Remote HTTP MCP",
    setupPlatform: "codex",
    installSteps: [
      "全域安裝可用 `antigravity --add-mcp`。",
      "repo 級安裝則編輯 `.vscode/mcp.json`。",
      "指向 ZenOS remote MCP endpoint。",
      "reload workspace 後再驗證。",
    ],
    setupSummary: [
      "ZenOS 目前沒有 Antigravity 專用 setup adapter，先走 codex-style instructions 最穩。",
      "頁面上要把 MCP 設定與治理 skill 說明拆開，不要假裝是一鍵完成。",
    ],
    ontologyStart: [
      "第一次上線既有 repo，一樣先 capture。",
      "治理修補則交給 sync / governance loop。",
    ],
    notes: [
      "目前找到的公開文件來自 Antigravity MCP 安裝指南。",
    ],
    sources: [
      {
        label: "Antigravity MCP install guide",
        href: "https://docs.zenable.io/integrations/mcp/ide/antigravity",
      },
    ],
    configExample: (apiKey) =>
      `antigravity --add-mcp '{"name":"zenos","url":"${STREAMABLE_HTTP_URL}?api_key=${apiKey}","type":"http"}'`,
  },
];

const STEP_RAIL = [
  {
    id: "mcp",
    label: "01",
    title: "先安裝 MCP",
    summary: "平台連線層。只解決 agent 如何接上 ZenOS。",
  },
  {
    id: "setup-tool",
    label: "02",
    title: "再安裝治理能力",
    summary: "用 setup tool 補上 skill、agent instructions、workflow。",
  },
  {
    id: "ontology",
    label: "03",
    title: "最後啟動 ontology",
    summary: "既有專案先 capture，再 sync，再治理。",
  },
];

function SetupPage() {
  const { partner } = useAuth();
  const router = useRouter();
  const { pushToast } = useToast();
  const [selectedPlatformId, setSelectedPlatformId] =
    useState<PlatformId>("claude-code");
  const { workspaceRole, isHomeWorkspace } = resolveActiveWorkspace(partner);
  const canManageWorkspace = isHomeWorkspace && workspaceRole === "owner";

  useEffect(() => {
    if (partner && !canManageWorkspace) {
      router.replace("/tasks");
    }
  }, [partner, canManageWorkspace, router]);

  if (!canManageWorkspace) return null;

  const selectedPlatform =
    PLATFORM_INSTALLS.find((item) => item.id === selectedPlatformId) ??
    PLATFORM_INSTALLS[0];

  const copyText = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    pushToast({
      tone: "success",
      title: `${label} copied`,
      description: "可以直接貼到對應 client 的設定位置。",
    });
  };

  return (
    <div className="min-h-screen">
      <AppNav />

      <main
        id="main-content"
        className="mx-auto grid max-w-7xl gap-8 px-6 py-8 lg:grid-cols-[260px_minmax(0,1fr)]"
      >
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="rounded-[28px] border border-border bg-card p-5">
            <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
              Setup Flow
            </p>
            <h1 className="mt-3 text-2xl font-semibold text-foreground">
              ZenOS onboarding
            </h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              把平台連線、治理安裝、專案建庫拆開。使用者只需要沿著這三步走，不需要自己理解整套內部名詞。
            </p>

            <div className="mt-6 space-y-3">
              {STEP_RAIL.map((step) => (
                <a
                  key={step.id}
                  href={`#${step.id}`}
                  className="block rounded-2xl border border-border bg-background/70 px-4 py-4 transition-colors hover:border-foreground/20"
                >
                  <div className="flex items-center gap-3">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15 text-xs font-semibold text-emerald-200">
                      {step.label}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {step.title}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {step.summary}
                      </p>
                    </div>
                  </div>
                </a>
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-emerald-200">
                Current platform
              </p>
              <p className="mt-2 text-lg font-semibold text-foreground">
                {selectedPlatform.name}
              </p>
              <p className="mt-2 text-sm text-emerald-50/85">
                setup tool 會使用 `{selectedPlatform.setupPlatform}` adapter。
              </p>
            </div>
          </div>
        </aside>

        <div className="space-y-8">
          <section className="rounded-[28px] border border-border bg-card p-6">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div className="max-w-3xl">
                <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
                  Platform
                </p>
                <h2 className="mt-2 text-3xl font-semibold text-foreground">
                  先選你要支援哪個 agent client
                </h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  右側所有步驟會跟著平台切換。這樣頁面不需要一次攤開六種安裝方式，閱讀成本會低很多。
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {PLATFORM_INSTALLS.map((platform) => {
                  const active = platform.id === selectedPlatform.id;
                  return (
                    <button
                      key={platform.id}
                      onClick={() => setSelectedPlatformId(platform.id)}
                      className={`rounded-full border px-4 py-2 text-sm transition-colors ${
                        active
                          ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100"
                          : "border-border bg-background/70 text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {platform.name}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          <section
            id="mcp"
            className="rounded-[28px] border border-border bg-card p-6"
          >
            <div className="flex flex-col gap-6 xl:flex-row xl:justify-between">
              <div className="max-w-2xl">
                <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
                  Step 1
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">
                  安裝 {selectedPlatform.name} 的 MCP 連線
                </h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  這一步只處理 ZenOS server 怎麼被 client 看見。技能、agent、workflow 都先不要談。
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[360px]">
                <InfoPill label="Config" value={selectedPlatform.configPath} />
                <InfoPill label="Mode" value={selectedPlatform.mcpMode} />
              </div>
            </div>

            <div className="mt-6 grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <div className="rounded-2xl border border-border bg-background/70 p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
                  Install path
                </p>
                <ol className="mt-4 space-y-3 text-sm text-muted-foreground">
                  {selectedPlatform.installSteps.map((step, index) => (
                    <li key={step} className="flex gap-3">
                      <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-foreground/8 text-xs font-medium text-foreground">
                        {index + 1}
                      </span>
                      <span className="leading-6">{step}</span>
                    </li>
                  ))}
                </ol>

                {selectedPlatform.notes?.length ? (
                  <div className="mt-5 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-amber-200">
                      Caveats
                    </p>
                    <div className="mt-2 space-y-2 text-sm text-amber-50/85">
                      {selectedPlatform.notes.map((note) => (
                        <p key={note}>{note}</p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <div
                data-testid="mcp-config"
                className="rounded-2xl border border-border bg-[#0f1418] p-5"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">
                      Ready to paste
                    </p>
                    <p className="mt-1 text-sm text-slate-200">
                      {selectedPlatform.badge}
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      copyText(
                        selectedPlatform.configExample(partner!.apiKey),
                        `${selectedPlatform.name} config`
                      )
                    }
                    className="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-slate-500 hover:bg-slate-800"
                  >
                    Copy config
                  </button>
                </div>

                <pre className="mt-4 overflow-x-auto rounded-2xl border border-slate-800 bg-black/30 p-4 text-xs leading-6 text-slate-100">
                  {selectedPlatform.configExample(partner!.apiKey)}
                </pre>

                <div className="mt-4 flex flex-wrap gap-3 text-sm">
                  {selectedPlatform.sources.map((source) => (
                    <a
                      key={source.href}
                      href={source.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-300 hover:underline"
                    >
                      {source.label}
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section
            id="setup-tool"
            className="rounded-[28px] border border-border bg-card p-6"
          >
            <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
              <div>
                <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
                  Step 2
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">
                  用 setup tool 安裝對應治理能力
                </h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  現在頁面會只顯示 {selectedPlatform.name} 對應的 setup adapter。
                  不再讓使用者自己猜該用 `claude_code`、`claude_web` 還是 `codex`。
                </p>

                <div className="mt-5 space-y-3">
                  {selectedPlatform.setupSummary.map((line, index) => (
                    <div
                      key={line}
                      className="rounded-2xl border border-border bg-background/70 p-4"
                    >
                      <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
                        Action {index + 1}
                      </p>
                      <p className="mt-2 text-sm text-foreground">{line}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5">
                <p className="text-xs uppercase tracking-[0.22em] text-emerald-200">
                  Recommended call
                </p>
                <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl border border-emerald-400/20 bg-black/15 p-4">
                  <code className="text-sm text-emerald-50">
                    setup(platform=&quot;{selectedPlatform.setupPlatform}&quot;)
                  </code>
                  <button
                    onClick={() =>
                      copyText(
                        `setup(platform="${selectedPlatform.setupPlatform}")`,
                        "Setup call"
                      )
                    }
                    className="rounded-full border border-emerald-300/20 px-3 py-1.5 text-xs font-medium text-emerald-50 hover:bg-emerald-500/10"
                  >
                    Copy call
                  </button>
                </div>

                <p className="mt-4 text-sm leading-6 text-emerald-50/85">
                  {selectedPlatform.setupPlatform === "claude_code" &&
                    "這個 adapter 會回傳 project-level skills、slash commands、CLAUDE.md addition。"}
                  {selectedPlatform.setupPlatform === "claude_web" &&
                    "這個 adapter 會回傳 Project Instructions 與文件上傳提示，適合 connector 型平台。"}
                  {selectedPlatform.setupPlatform === "codex" &&
                    "這個 adapter 目前也作為 Codex 以外平台的 fallback，用來提供 AGENTS / instruction style 治理入口。"}
                </p>

                <Link
                  href="/setup/skills"
                  className="mt-5 inline-flex rounded-full border border-emerald-300/20 px-4 py-2 text-sm font-medium text-emerald-50 hover:bg-emerald-500/10"
                >
                  查看 skills / agents / flows
                </Link>
              </div>
            </div>
          </section>

          <section
            id="ontology"
            className="rounded-[28px] border border-border bg-card p-6"
          >
            <p className="text-xs uppercase tracking-[0.26em] text-muted-foreground">
              Step 3
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">
              既有專案怎麼開始 ZenOS ontology
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              onboarding 的關鍵不是工具名稱，而是順序。第一次建庫和日常同步是兩條不同流程，頁面需要明講。
            </p>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              {selectedPlatform.ontologyStart.map((line, index) => (
                <div
                  key={line}
                  className="rounded-2xl border border-border bg-background/70 p-5"
                >
                  <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
                    Rule {index + 1}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-foreground">
                    {line}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-blue-500/30 bg-blue-500/10 p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-blue-200">
                Canonical sequence
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-5">
                {[
                  "選平台並接 MCP",
                  "跑 setup tool",
                  "首次用 zenos-capture",
                  "後續用 zenos-sync",
                  "需要修補時進 governance",
                ].map((item, index) => (
                  <div
                    key={item}
                    className="rounded-2xl border border-blue-400/15 bg-black/10 p-4"
                  >
                    <p className="text-xs text-blue-200/70">0{index + 1}</p>
                    <p className="mt-2 text-sm text-blue-50">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <div className="flex justify-between text-sm">
            <Link href="/" className="text-blue-400 hover:underline">
              Back to projects
            </Link>
            <Link href="/setup/skills" className="text-blue-400 hover:underline">
              Skills / agents / flows
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background/70 px-4 py-3">
      <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm text-foreground">{value}</p>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <SetupPage />
    </AuthGuard>
  );
}
