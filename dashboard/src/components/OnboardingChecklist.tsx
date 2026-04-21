"use client";

import { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import type { OnboardingPreferences } from "@/types";

// ─── Constants ───

type StepStatus = "done" | "skipped" | "pending";

interface StepConfig {
  id: string;
  title: string;
  subtitle: string;
}

const STEPS: StepConfig[] = [
  { id: "step1", title: "導向知識庫", subtitle: "告訴 AI 你的知識在哪裡" },
  { id: "step2", title: "設定 MCP + 安裝 Skills", subtitle: "讓 AI 連上 ZenOS" },
  { id: "step3", title: "捕捉知識", subtitle: "用 AI 把知識匯入知識地圖" },
  { id: "step4", title: "體驗 AI 角色", subtitle: "讓 AI 用你的知識來工作" },
];

// ─── Types ───

/** Platform IDs that require SSE transport instead of streamable-HTTP */
const SSE_PLATFORMS = new Set(["gemini-cli", "antigravity"]);

interface OnboardingChecklistProps {
  /** Whether partner account exists (Step 2 auto-complete) */
  hasPartner: boolean;
  /** Whether workspace has entities (Step 3 auto-complete) */
  hasEntities: boolean;
  /** Persisted onboarding preferences from server */
  onboardingPrefs: OnboardingPreferences;
  /** Partner API key for MCP URL display */
  apiKey: string;
  /** Callback to update preferences on server */
  onUpdatePrefs: (patch: OnboardingPreferences) => void;
  /** Platform type for copy differentiation */
  platformType: "technical" | "non_technical";
  /** Selected platform ID for transport detection */
  platformId?: string;
}

// ─── Step Content Components ───

function Step1Content({
  platformType,
  onDone,
  onSkip,
}: {
  platformType: "technical" | "non_technical";
  onDone: () => void;
  onSkip: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const technicalContent = {
    description: "在開始之前，先讓 AI 知道你的專案在哪裡。指向本地資料夾或 Google Drive，AI 才能讀取你的知識。",
    instruction: "告訴 AI 你的專案路徑：",
    command: "我的專案在 ~/my-project，請幫我整理到 ZenOS",
    driveHint: "如果知識在 Google Drive，先在 AI 工具中安裝 Google Drive MCP，讓 AI 能讀取雲端文件。",
  };

  const nonTechnicalContent = {
    description: "先告訴 AI 助手你的資料放在哪裡——可以是電腦上的資料夾，或是 Google Drive 上的文件。",
    instruction: "告訴你的 AI 助手：",
    command: "我的公司資料在 Google Drive 的「公司文件」資料夾裡，請幫我整理",
    driveHint: "如果資料在 Google Drive，AI 助手會引導你設定 Google Drive 連結。",
  };

  const content = platformType === "technical" ? technicalContent : nonTechnicalContent;

  const copyCommand = useCallback(async () => {
    await navigator.clipboard.writeText(content.command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content.command]);

  return (
    <div className="space-y-3">
      <p className="text-sm text-dim">{content.description}</p>
      <p className="text-xs font-medium text-foreground">{content.instruction}</p>
      <div className="rounded-lg border bd-hair bg-[#0f1418] p-3">
        <div className="flex items-center justify-between gap-2">
          <code className="text-sm text-emerald-300">{content.command}</code>
          <button
            onClick={copyCommand}
            className="shrink-0 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
      <p className="text-xs text-dim">{content.driveHint}</p>
      <div className="flex gap-2 pt-1">
        <button
          onClick={onDone}
          className="rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
        >
          已完成
        </button>
        <button
          onClick={onSkip}
          className="rounded-full border bd-hair px-4 py-1.5 text-xs text-dim hover:text-foreground"
        >
          稍後再說
        </button>
      </div>
    </div>
  );
}

const MCP_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";

function Step2Content({ apiKey, useSSE }: { apiKey: string; useSSE: boolean }) {
  const endpoint = useSSE ? "sse" : "mcp";
  const mcpUrl = `${MCP_BASE}/${endpoint}?api_key=${apiKey}`;
  const maskedUrl = `${MCP_BASE}/${endpoint}?api_key=${apiKey.slice(0, 8)}........`;

  const [copied, setCopied] = useState(false);
  const copyUrl = useCallback(async () => {
    await navigator.clipboard.writeText(mcpUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [mcpUrl]);

  return (
    <div className="space-y-3">
      <p className="text-sm text-dim">
        將 MCP 連結加入你的 AI 工具，然後安裝 ZenOS skills，讓 AI 獲得角色和治理能力。
      </p>
      <div className="rounded-lg border bd-hair bg-[#0f1418] p-3">
        <div className="flex items-center justify-between gap-2">
          <code className="text-xs text-slate-300 break-all">{maskedUrl}</code>
          <button
            onClick={copyUrl}
            className="shrink-0 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
      <p className="text-xs text-dim">
        連上 MCP 後，在 AI 工具中輸入 <code className="text-emerald-300">/zenos-setup</code> 來安裝 Skills。
      </p>
      <Link href="/setup" className="inline-block text-xs text-blue-400 hover:underline">
        前往完整設定頁面
      </Link>
    </div>
  );
}

function Step3Content({ platformType }: { platformType: "technical" | "non_technical" }) {
  const [copied, setCopied] = useState(false);

  const technicalContent = {
    instruction: "在你的 AI 工具（如 Claude Code）中執行以下指令：",
    command: "/zenos-capture ~/your-project",
    hint: "將 ~/your-project 替換為你的專案目錄路徑。AI 會自動掃描專案結構，建立知識地圖。",
  };

  const nonTechnicalContent = {
    instruction: "告訴你的 AI 助手（如 Claude.ai）：",
    command: "幫我把這個專案加入 ZenOS，用 /zenos-capture 建立知識庫",
    hint: "AI 助手會引導你完成後續步驟。完成後，知識地圖就會出現你的專案節點。",
  };

  const content = platformType === "technical" ? technicalContent : nonTechnicalContent;

  const copyCommand = useCallback(async () => {
    await navigator.clipboard.writeText(content.command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content.command]);

  return (
    <div className="space-y-3">
      <p className="text-sm text-dim">{content.instruction}</p>
      <div className="rounded-lg border bd-hair bg-[#0f1418] p-3">
        <div className="flex items-center justify-between gap-2">
          <code className="text-sm text-emerald-300">{content.command}</code>
          <button
            onClick={copyCommand}
            className="shrink-0 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
      <p className="text-xs text-dim">{content.hint}</p>
    </div>
  );
}

function Step4Content({
  onDone,
  onSkip,
}: {
  onDone: () => void;
  onSkip: () => void;
}) {
  const roles = [
    {
      name: "/pm",
      label: "產品需求",
      example: "用 /pm 幫我規劃一個新功能的需求",
    },
    {
      name: "/architect",
      label: "技術規劃",
      example: "用 /architect 幫我分析這個系統的架構",
    },
    {
      name: "/marketing",
      label: "內容行銷",
      example: "用 /marketing 幫我寫一篇產品介紹文案",
    },
  ];

  return (
    <div className="space-y-3">
      <p className="text-sm text-dim">
        試試用 AI 角色來處理工作。這些角色會根據知識地圖中的資訊來理解你的公司。
      </p>
      <div className="space-y-2">
        {roles.map((role) => (
          <div
            key={role.name}
            className="rounded-lg border bd-hair bg-base p-3"
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold text-emerald-300">
                {role.name}
              </span>
              <span className="text-xs text-dim">{role.label}</span>
            </div>
            <p className="mt-1 text-xs text-dim">
              試試看：「{role.example}」
            </p>
          </div>
        ))}
      </div>
      <p className="text-xs text-dim">
        如果沒有看到這些角色，請先在 AI 工具中執行 <code className="text-emerald-300">/zenos-setup</code> 安裝 ZenOS Agent。
      </p>
      <div className="flex gap-2 pt-1">
        <button
          onClick={onDone}
          className="rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
        >
          已完成
        </button>
        <button
          onClick={onSkip}
          className="rounded-full border bd-hair px-4 py-1.5 text-xs text-dim hover:text-foreground"
        >
          稍後再說
        </button>
      </div>
    </div>
  );
}

// ─── Checklist Step Wrapper ───

function ChecklistStep({
  step,
  index,
  status,
  expanded,
  onToggle,
  children,
}: {
  step: StepConfig;
  index: number;
  status: StepStatus;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b bd-hair last:border-b-0">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-foreground/5 transition-colors cursor-pointer"
      >
        {/* Status indicator */}
        <div className="shrink-0">
          {status === "done" ? (
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/20">
              <svg className="h-3.5 w-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          ) : status === "skipped" ? (
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-foreground/10">
              <span className="text-xs text-dim">--</span>
            </div>
          ) : (
            <div className="flex h-6 w-6 items-center justify-center rounded-full border bd-hair">
              <span className="text-xs text-dim">{index + 1}</span>
            </div>
          )}
        </div>

        {/* Title */}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${status === "done" ? "text-emerald-300" : "text-foreground"}`}>
            {step.title}
          </p>
          <p className="text-xs text-dim">{step.subtitle}</p>
        </div>

        {/* Expand arrow */}
        <svg
          className={`h-4 w-4 text-dim transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-5 pb-4 pl-14">
          {children}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───

export function OnboardingChecklist({
  hasPartner,
  hasEntities,
  onboardingPrefs,
  apiKey,
  onUpdatePrefs,
  platformType,
  platformId,
}: OnboardingChecklistProps) {
  const useSSE = platformId ? SSE_PLATFORMS.has(platformId) : false;
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const stepStatuses: Record<string, StepStatus> = useMemo(() => ({
    step1: onboardingPrefs.step1_done ? "done" : "pending",
    step2: hasPartner ? "done" : "pending",
    step3: hasEntities ? "done" : "pending",
    step4: onboardingPrefs.step4_done ? "done" : "pending",
  }), [onboardingPrefs.step1_done, hasPartner, hasEntities, onboardingPrefs.step4_done]);

  const doneCount = Object.values(stepStatuses).filter((s) => s === "done").length;
  const totalSteps = STEPS.length;
  const progressPct = Math.round((doneCount / totalSteps) * 100);

  const handleToggle = useCallback((stepId: string) => {
    setExpandedStep((prev) => (prev === stepId ? null : stepId));
  }, []);

  const handleStep1Done = useCallback(() => {
    onUpdatePrefs({ step1_done: true });
  }, [onUpdatePrefs]);

  const handleStep1Skip = useCallback(() => {
    setExpandedStep(null);
  }, []);

  const handleStep4Done = useCallback(() => {
    onUpdatePrefs({ step4_done: true });
  }, [onUpdatePrefs]);

  const handleStep4Skip = useCallback(() => {
    setExpandedStep(null);
  }, []);

  const handleDismiss = useCallback(() => {
    onUpdatePrefs({ dismissed: true });
  }, [onUpdatePrefs]);

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="rounded-[28px] border bd-hair bg-panel overflow-hidden">
        {/* Header */}
        <div className="px-5 pt-5 pb-4">
          <h2 className="text-lg font-semibold text-foreground">
            開始使用 ZenOS
          </h2>
          <p className="mt-1 text-sm text-dim">
            完成以下步驟，讓 AI 助手理解你的公司
          </p>

          {/* Progress bar */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 h-1.5 rounded-full bg-foreground/10">
              <div
                className="h-1.5 rounded-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-xs text-dim shrink-0">
              {doneCount}/{totalSteps}
            </span>
          </div>
        </div>

        {/* Steps */}
        <div className="border-t bd-hair">
          {STEPS.map((step, index) => (
            <ChecklistStep
              key={step.id}
              step={step}
              index={index}
              status={stepStatuses[step.id]}
              expanded={expandedStep === step.id}
              onToggle={() => handleToggle(step.id)}
            >
              {step.id === "step1" && (
                <Step1Content
                  platformType={platformType}
                  onDone={handleStep1Done}
                  onSkip={handleStep1Skip}
                />
              )}
              {step.id === "step2" && <Step2Content apiKey={apiKey} useSSE={useSSE} />}
              {step.id === "step3" && <Step3Content platformType={platformType} />}
              {step.id === "step4" && (
                <Step4Content onDone={handleStep4Done} onSkip={handleStep4Skip} />
              )}
            </ChecklistStep>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t bd-hair px-5 py-3 flex justify-end">
          <button
            onClick={handleDismiss}
            className="text-xs text-dim hover:text-foreground transition-colors"
          >
            不再顯示
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Empty State Button ───

export function OnboardingStartButton({ onClick }: { onClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16">
      <div className="rounded-full bg-emerald-500/10 p-4">
        <svg className="h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
        </svg>
      </div>
      <div className="text-center">
        <h2 className="text-lg font-semibold text-foreground">
          你的知識地圖還是空的
        </h2>
        <p className="mt-1 text-sm text-dim max-w-xs">
          讓我們一起把你的專案知識加入 ZenOS，讓 AI 助手真正理解你的公司
        </p>
      </div>
      <button
        onClick={onClick}
        className="rounded-full bg-emerald-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
      >
        開始使用
      </button>
    </div>
  );
}
