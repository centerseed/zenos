"use client";

/**
 * CrmAiPanel — AI Briefing and Debrief panel for Deal detail page.
 *
 * Uses the shared copilot infrastructure:
 *   useCopilotChat hook + CopilotRailShell + CopilotChatViewport + CopilotInputBar
 *
 * CRM-specific logic (context pack building, follow-up parsing, stage advance)
 * is preserved here; streaming mechanics are delegated to the hook.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Copy, Check, PlugZap } from "lucide-react";
import { Button } from "@/components/zen/legacy";
import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import { CopilotChatViewport } from "@/components/ai/CopilotChatViewport";
import { CopilotInputBar } from "@/components/ai/CopilotInputBar";
import { useCopilotChat } from "@/lib/copilot/useCopilotChat";
import { resolveCopilotWorkspaceId } from "@/lib/copilot/scope";
import type { CopilotEntryConfig } from "@/lib/copilot/types";
import type { Partner } from "@/types";
import { sanitizeContextValue } from "@/config/ai-redaction-rules";
import type { Deal, Activity, Company, Contact, FunnelStage, DealAiEntries } from "@/lib/crm-api";
import { patchDealStage } from "@/lib/crm-api";

// ─── Types ─────────────────────────────────────────────────────────────────────

type AiMode = "briefing" | "debrief";

interface FollowUpDraft {
  line: string;
  email: { subject: string; body: string };
}

export interface CrmAiPanelProps {
  mode: AiMode;
  deal: Deal;
  activities: Activity[];
  company: Company | null;
  contacts: Contact[];
  token: string;
  /** For debrief: the newly created activity that triggered debrief */
  triggerActivity?: Activity;
  onStageAdvanced?: (deal: Deal) => void;
  onClose?: () => void;
  /** Called with the complete AI text when streaming finishes (debrief mode) */
  onStreamComplete?: (finalText: string) => void;
  /** AI entries from DealDetailClient for enriching briefing context pack */
  aiEntries?: DealAiEntries | null;
}

// ─── Context pack helpers ──────────────────────────────────────────────────────

/**
 * Build a summary of recent activities (≤1500 chars) from newest to oldest.
 */
function buildActivitiesSummary(activities: Activity[]): string {
  const sorted = [...activities]
    .filter((a) => !a.isSystem)
    .sort((a, b) => b.activityAt.getTime() - a.activityAt.getTime())
    .slice(0, 10);

  const lines = sorted.map((a) => {
    const dateStr =
      a.activityAt instanceof Date
        ? a.activityAt.toLocaleDateString("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit" })
        : String(a.activityAt);
    return `[${dateStr}] ${a.activityType}: ${a.summary}`;
  });

  let result = lines.join("\n");
  if (result.length > 1500) result = result.slice(0, 1497) + "...";
  return result;
}

/**
 * Build the briefing context pack and format it as a prompt string.
 * Context pack is sanitized with redaction rules and capped at 2000 chars.
 */
function buildBriefingPrompt(
  deal: Deal,
  activities: Activity[],
  company: Company | null,
  contacts: Contact[],
  aiEntries?: DealAiEntries | null
): string {
  const debriefInsights = aiEntries
    ? {
        key_decisions: aiEntries.debriefs.flatMap(
          (d) => (d.metadata as Record<string, unknown>).key_decisions as string[] ?? []
        ),
        customer_concerns: aiEntries.debriefs.flatMap(
          (d) => (d.metadata as Record<string, unknown>).customer_concerns as string[] ?? []
        ),
        open_commitments: aiEntries.commitments
          .filter((c) => c.status === "open")
          .map((c) => ({
            content: (c.metadata as Record<string, unknown>).content as string ?? "",
            owner: (c.metadata as Record<string, unknown>).owner as string ?? "us",
            deadline: (c.metadata as Record<string, unknown>).deadline as string ?? "",
          })),
      }
    : undefined;

  const contextPack = {
    scene: "briefing",
    deal_id: deal.id,
    company: company
      ? {
          name: company.name,
          industry: company.industry ?? null,
          size_range: company.sizeRange ?? null,
          region: company.region ?? null,
        }
      : { name: "—" },
    deal: {
      title: deal.title,
      funnel_stage: deal.funnelStage,
      deal_type: deal.dealType ?? null,
      source_type: deal.sourceType ?? null,
      amount_twd: deal.amountTwd ?? null,
      scope_description: deal.scopeDescription ?? null,
      deliverables: deal.deliverables ?? [],
    },
    activities_summary: buildActivitiesSummary(activities),
    contacts: contacts.map((c) => ({ name: c.name, title: c.title ?? null })),
    previous_briefings_count: 0,
    ...(debriefInsights !== undefined ? { debrief_insights: debriefInsights } : {}),
    suggested_skill: "/crm-briefing",
  };

  const sanitized = sanitizeContextValue(contextPack);
  let packed = JSON.stringify(sanitized, null, 2);
  if (packed.length > 2000) {
    const truncatedPack = { ...(sanitized as Record<string, unknown>), activities_summary: "（摘要過長，已截斷）" };
    packed = JSON.stringify(truncatedPack, null, 2);
  }

  return `/crm-briefing\n\n以下是此商機的背景資料（JSON），請準備會議 briefing：\n\n${packed}`;
}

/**
 * Build the debrief context pack and format it as a prompt string.
 */
function buildDebriefPrompt(
  deal: Deal,
  company: Company | null,
  triggerActivity: Activity,
  aiEntries?: DealAiEntries | null
): string {
  const contextPack = {
    scene: "debrief",
    deal_id: deal.id,
    company_name: company?.name ?? "—",
    deal_title: deal.title,
    funnel_stage: deal.funnelStage,
    activity: {
      type: triggerActivity.activityType,
      summary: triggerActivity.summary,
    },
    recent_commitments: aiEntries?.commitments
      ?.filter((c) => c.status === "open")
      ?.map((c) => (c.metadata as Record<string, unknown>)?.content as string ?? "")
      ?.filter(Boolean)
      ?? [],
    suggested_skill: "/crm-debrief",
  };

  const sanitized = sanitizeContextValue(contextPack);
  let packed = JSON.stringify(sanitized, null, 2);
  if (packed.length > 2000) {
    packed = JSON.stringify(sanitized);
  }

  return `/crm-debrief\n\n以下是此次活動的背景資料（JSON），請進行 debrief 並生成 follow-up 草稿：\n\n${packed}`;
}

/**
 * Extract LINE and Email follow-up sections from completed AI markdown output.
 * Looks for ## LINE and ## Email (or similar headings).
 */
function extractFollowUpDraft(markdown: string): FollowUpDraft | null {
  const lineMatch = markdown.match(/##\s*(?:LINE|Line|line)[^\n]*\n([\s\S]*?)(?=##|$)/);
  const emailMatch = markdown.match(/##\s*(?:Email|email|電子郵件|郵件)[^\n]*\n([\s\S]*?)(?=##|$)/);

  if (!lineMatch && !emailMatch) return null;

  const lineContent = lineMatch ? lineMatch[1].trim() : "";

  let emailSubject = "";
  let emailBody = "";
  if (emailMatch) {
    const emailContent = emailMatch[1].trim();
    const subjectMatch = emailContent.match(/(?:\*\*主旨[:：]\*\*|主旨[:：])\s*(.+)/);
    if (subjectMatch) {
      emailSubject = subjectMatch[1].trim();
      emailBody = emailContent.replace(subjectMatch[0], "").trim();
    } else {
      const lines = emailContent.split("\n");
      emailSubject = lines[0].replace(/^[*#\-\s]+/, "").trim();
      emailBody = lines.slice(1).join("\n").trim();
    }
  }

  return {
    line: lineContent,
    email: { subject: emailSubject, body: emailBody },
  };
}

// ─── CrmAiPanel entry factories ───────────────────────────────────────────────

function createBriefingEntry(params: {
  partner?: Partner | null;
  deal: Deal;
  activities: Activity[];
  company: Company | null;
  contacts: Contact[];
  aiEntries?: DealAiEntries | null;
}): CopilotEntryConfig {
  return {
    intent_id: "crm-briefing",
    title: "AI 會議準備",
    mode: "chat",
    launch_behavior: "manual",
    session_policy: "scoped_resume",
    suggested_skill: "/crm-briefing",
    claude_code_bootstrap: {
      use_project_claude_config: true,
      required_skills: [
        "/crm-briefing",
        "/zenos-governance",
        "skills/governance/task-governance.md",
        "skills/governance/document-governance.md",
      ],
      governance_topics: ["task", "document"],
      verify_zenos_write: true,
      execution_contract: [
        "Use the workspace-local .claude settings and MCP config for this deal scope.",
        "Load task/document governance before any ZenOS mutation.",
        "If CRM follow-up work spans multiple ordered steps, create a real plan first and attach tasks with plan_id and plan_order instead of using parent tasks as a fake plan.",
        "Re-fetch created or updated ZenOS records before claiming success.",
      ],
    },
    scope: {
      workspace_id: resolveCopilotWorkspaceId(params.partner),
      deal_id: params.deal.id,
      entity_ids: [params.deal.id],
      scope_label: params.deal.title,
    },
    context_pack: { scene: "briefing", deal_id: params.deal.id },
    write_targets: [],
    build_prompt: (userInput: string) => {
      if (userInput) {
        return `/crm-briefing\n\n使用者追問：\n${userInput}\n\n請根據之前的 briefing context 回答。`;
      }
      return buildBriefingPrompt(params.deal, params.activities, params.company, params.contacts, params.aiEntries);
    },
  };
}

function createDebriefEntry(params: {
  partner?: Partner | null;
  deal: Deal;
  company: Company | null;
  triggerActivity: Activity;
  aiEntries?: DealAiEntries | null;
}): CopilotEntryConfig {
  return {
    intent_id: "crm-debrief",
    title: "AI 活動 Debrief",
    mode: "chat",
    launch_behavior: "auto_start",
    session_policy: "ephemeral",
    suggested_skill: "/crm-debrief",
    claude_code_bootstrap: {
      use_project_claude_config: true,
      required_skills: [
        "/crm-debrief",
        "/zenos-governance",
        "skills/governance/task-governance.md",
        "skills/governance/document-governance.md",
      ],
      governance_topics: ["task", "document"],
      verify_zenos_write: true,
      execution_contract: [
        "Use the workspace-local .claude settings and MCP config for this deal scope.",
        "Load task/document governance before any ZenOS mutation.",
        "If CRM follow-up work spans multiple ordered steps, create a real plan first and attach tasks with plan_id and plan_order instead of using parent tasks as a fake plan.",
        "Re-fetch created or updated ZenOS records before claiming success.",
      ],
    },
    scope: {
      workspace_id: resolveCopilotWorkspaceId(params.partner),
      deal_id: params.deal.id,
      entity_ids: [params.deal.id],
      scope_label: params.deal.title,
    },
    context_pack: { scene: "debrief", deal_id: params.deal.id },
    write_targets: [],
    build_prompt: (_userInput: string) =>
      buildDebriefPrompt(params.deal, params.company, params.triggerActivity, params.aiEntries),
  };
}

// ─── CopyButton ──────────────────────────────────────────────────────────────

function CopyButton({ text, className = "" }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may be denied in some browser contexts — silent fail
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors ${className}`}
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-green-400" />
          已複製
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          複製
        </>
      )}
    </button>
  );
}

// ─── FollowUpDraftUI ─────────────────────────────────────────────────────────

function FollowUpDraftUI({ draft }: { draft: FollowUpDraft }) {
  const [activeTab, setActiveTab] = useState<"line" | "email">("line");
  const [lineText, setLineText] = useState(draft.line);
  const [emailSubject, setEmailSubject] = useState(draft.email.subject);
  const [emailBody, setEmailBody] = useState(draft.email.body);

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-border bg-secondary/30">
        <button
          onClick={() => setActiveTab("line")}
          className={`px-4 py-2 text-xs font-medium transition-colors ${
            activeTab === "line"
              ? "bg-background text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          LINE
        </button>
        <button
          onClick={() => setActiveTab("email")}
          className={`px-4 py-2 text-xs font-medium transition-colors ${
            activeTab === "email"
              ? "bg-background text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Email
        </button>
      </div>

      {/* Tab content */}
      <div className="p-3 space-y-2">
        {activeTab === "line" ? (
          <>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">LINE 訊息草稿</span>
              <CopyButton text={lineText} />
            </div>
            <textarea
              value={lineText}
              onChange={(e) => setLineText(e.target.value)}
              rows={6}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none font-mono"
            />
          </>
        ) : (
          <>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Email 草稿</span>
              <CopyButton text={`主旨：${emailSubject}\n\n${emailBody}`} />
            </div>
            <div className="space-y-2">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">主旨</label>
                <input
                  type="text"
                  value={emailSubject}
                  onChange={(e) => setEmailSubject(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">正文</label>
                <textarea
                  value={emailBody}
                  onChange={(e) => setEmailBody(e.target.value)}
                  rows={8}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── StageAdvanceButton ──────────────────────────────────────────────────────

interface StageAdvanceButtonProps {
  deal: Deal;
  token: string;
  onAdvanced: (updated: Deal) => void;
}

const STAGE_ORDER: FunnelStage[] = ["潛在客戶", "需求訪談", "提案報價", "合約議價", "導入中", "結案"];

function StageAdvanceButton({ deal, token, onAdvanced }: StageAdvanceButtonProps) {
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentIndex = STAGE_ORDER.indexOf(deal.funnelStage);
  const nextStage = currentIndex >= 0 && currentIndex < STAGE_ORDER.length - 1 ? STAGE_ORDER[currentIndex + 1] : null;

  if (!nextStage) return null;

  async function handleAdvance() {
    if (!nextStage) return;
    setAdvancing(true);
    setError(null);
    try {
      const updated = await patchDealStage(token, deal.id, nextStage);
      onAdvanced(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新失敗");
    }
    setAdvancing(false);
  }

  return (
    <div className="space-y-1">
      <button
        onClick={handleAdvance}
        disabled={advancing}
        className="px-4 py-2 text-sm rounded-lg bg-primary/15 text-primary border border-primary/30 hover:bg-primary/25 transition-colors disabled:opacity-50"
      >
        {advancing ? "更新中..." : `推進到「${nextStage}」`}
      </button>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

// ─── Offline warning ──────────────────────────────────────────────────────────

function OfflineWarning({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="m-4 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
      <PlugZap className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
      <div className="text-sm text-amber-300">
        <p className="font-medium">Local Helper 未連線</p>
        <p className="text-xs text-amber-400 mt-0.5">請先啟動 Local Helper（port 4317），再重試。</p>
      </div>
      <button
        onClick={onRetry}
        className="ml-auto shrink-0 px-3 py-1 text-xs rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors"
      >
        重試
      </button>
    </div>
  );
}

// ─── CrmAiPanel ──────────────────────────────────────────────────────────────

export function CrmAiPanel({
  mode,
  deal,
  activities,
  company,
  contacts,
  token,
  triggerActivity,
  onStageAdvanced,
  onClose,
  onStreamComplete,
  aiEntries,
}: CrmAiPanelProps) {
  // Build the entry config based on mode
  const entry = useMemo<CopilotEntryConfig | null>(() => {
    if (mode === "briefing") {
      return createBriefingEntry({ deal, activities, company, contacts, aiEntries });
    }
    if (triggerActivity) {
      return createDebriefEntry({ deal, company, triggerActivity, aiEntries });
    }
    return null;
  }, [mode, deal, activities, company, contacts, triggerActivity, aiEntries]);

  const chat = useCopilotChat(entry);
  const [open, setOpen] = useState(true);

  // Debrief: auto-start exactly once when connector first becomes ready
  const debriefAutoStartedRef = useRef(false);
  useEffect(() => {
    if (
      mode === "debrief" &&
      triggerActivity &&
      chat.connectorStatus === "connected" &&
      !debriefAutoStartedRef.current &&
      chat.messages.length === 0 &&
      chat.status === "idle"
    ) {
      debriefAutoStartedRef.current = true;
      void chat.send("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, triggerActivity, chat.connectorStatus, chat.status]);

  // Briefing: first send uses empty input — build_prompt fills the context pack
  const handleStartBriefing = useCallback(() => {
    void chat.send("");
  }, [chat]);

  // Debrief: fire onStreamComplete when status transitions from running → idle
  const prevStatusRef = useRef(chat.status);
  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = chat.status;
    if (
      mode === "debrief" &&
      prev !== "idle" &&
      chat.status === "idle" &&
      chat.messages.length > 0
    ) {
      const lastAssistant = [...chat.messages].reverse().find((m) => m.role === "assistant");
      if (lastAssistant) {
        onStreamComplete?.(lastAssistant.content);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, chat.status, chat.messages, onStreamComplete]);

  // Extract follow-up draft from last assistant message (debrief only)
  const followUp = useMemo<FollowUpDraft | null>(() => {
    if (mode !== "debrief") return null;
    const lastAssistant = [...chat.messages].reverse().find((m) => m.role === "assistant");
    return lastAssistant ? extractFollowUpDraft(lastAssistant.content) : null;
  }, [mode, chat.messages]);

  const isStreaming = chat.status === "loading" || chat.status === "streaming";
  const hasChatContent = chat.messages.length > 0 || !!chat.streamingText;

  // Filter out system messages for the viewport (show only user/assistant)
  const visibleMessages = useMemo(
    () => chat.messages.filter((m) => m.role !== "system"),
    [chat.messages]
  );

  const inputBar =
    mode === "briefing" && hasChatContent ? (
      <CopilotInputBar
        status={chat.status}
        onSend={(input) => void chat.send(input)}
        onCancel={() => void chat.cancel()}
        onRetry={() => void chat.retry()}
        hasStructuredResult={false}
        placeholder="追問或調整重點..."
      />
    ) : undefined;

  return (
    <CopilotRailShell
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) onClose?.();
      }}
      entry={entry}
      chatStatus={chat.status}
      connectorStatus={chat.connectorStatus}
      desktopInline
      footer={inputBar}
    >
      {/* Briefing CTA — only before first message */}
      {mode === "briefing" && !hasChatContent && chat.status === "idle" && chat.connectorStatus !== "disconnected" && (
        <div className="p-4">
          <Button onClick={handleStartBriefing} className="w-full">
            <Bot className="mr-2 h-4 w-4" />
            準備下次會議
          </Button>
        </div>
      )}

      {/* Offline warning */}
      {chat.connectorStatus === "disconnected" && chat.status === "idle" && (
        <OfflineWarning onRetry={() => void chat.checkHealth()} />
      )}

      {/* Chat area */}
      {(hasChatContent || isStreaming) && (
        <CopilotChatViewport
          messages={visibleMessages}
          streamingText={chat.streamingText}
          isStreaming={isStreaming}
          emptyStateTitle={mode === "briefing" ? "AI 會議準備" : "AI 活動 Debrief"}
          emptyStateDescription="開始對話後，AI 回覆會顯示在這裡"
        />
      )}

      {/* Debrief-specific: follow-up draft + stage advance */}
      {mode === "debrief" && chat.status === "idle" && visibleMessages.length > 0 && (
        <div className="space-y-4 p-4">
          {followUp && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Follow-up 草稿</h4>
              <FollowUpDraftUI draft={followUp} />
            </div>
          )}
          {onStageAdvanced && (
            <div className="pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground mb-2">如 AI 建議推進漏斗階段：</p>
              <StageAdvanceButton deal={deal} token={token} onAdvanced={onStageAdvanced} />
            </div>
          )}
        </div>
      )}
    </CopilotRailShell>
  );
}
