"use client";

/**
 * CrmAiPanel — AI Briefing and Debrief panel for Deal detail page.
 *
 * Reuses cowork-helper.ts streamCoworkChat() for SSE streaming.
 * No AI logic lives here — only context pack assembly, display, and copy.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Copy, Check, RefreshCw, PlugZap, ChevronDown, ChevronUp } from "lucide-react";
import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import { GraphContextBadge } from "@/components/ai/GraphContextBadge";
import { CopilotChatViewport } from "@/components/ai/CopilotChatViewport";
import { CopilotInputBar } from "@/components/ai/CopilotInputBar";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import {
  cancelCoworkRequest,
  streamCoworkChat,
  checkCoworkHelperHealth,
  getDefaultHelperBaseUrl,
  getDefaultHelperToken,
  getDefaultHelperModel,
  getDefaultHelperCwd,
  CoworkCapabilityCheck,
  CoworkStreamEvent,
} from "@/lib/cowork-helper";
import { sanitizeContextValue } from "@/config/ai-redaction-rules";
import { useAuth } from "@/lib/auth";
import { resolveCopilotWorkspaceId } from "@/lib/copilot/scope";
import {
  clearSessionStarted,
  clearSessionSnapshot,
  markSessionStarted,
  readFreshSessionStartedAt,
  readFreshSessionSnapshot,
  writeSessionSnapshot,
} from "@/lib/copilot/session";
import type { GraphContextResponse } from "@/lib/api";
import { fetchGraphContext } from "@/lib/graph-context";
import { buildCrmKnowledgePrompt, COWORK_MAX_TURNS, graphContextUnavailableNotice } from "@/lib/cowork-knowledge";
import { parseStreamLine } from "@/lib/copilot/stream";
import type { Deal, Activity, Company, Contact, FunnelStage, DealAiEntries } from "@/lib/crm-api";
import { createAiInsight, patchDealStage, updateBriefing } from "@/lib/crm-api";
import type { AiInsight } from "@/lib/crm-api";
import { useInk } from "@/lib/zen-ink/tokens";
import { Tabs } from "@/components/zen/Tabs";
import { Textarea } from "@/components/zen/Textarea";
import { Input } from "@/components/zen/Input";
import { Btn } from "@/components/zen/Btn";

// ─── Types ─────────────────────────────────────────────────────────────────────

type AiMode = "briefing" | "debrief";
type AiStatus = "idle" | "loading" | "streaming" | "done" | "error";

interface FollowUpDraft {
  line: string;
  email: { subject: string; body: string };
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface BriefingMetadata {
  title?: string;
  conversation_id?: string;
  turn_count?: number;
  chat_history?: ChatMessage[];
  saved_at?: string;
  graph_context_seed?: string;
  graph_context_l2_count?: number;
  graph_context_l3_count?: number;
}

interface CrmCopilotSnapshot {
  status: AiStatus;
  streamingText: string;
  finalText: string;
  errorMsg: string | null;
  followUp: FollowUpDraft | null;
  permissionLabel: string | null;
  helperEvents: string[];
  chatHistory: ChatMessage[];
  turnCount: number;
  requestId: string | null;
  userInput: string;
}

interface CrmAiPanelProps {
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
  initialBriefing?: AiInsight | null;
  onBriefingSaved?: (saved: AiInsight, mode: "create" | "update") => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function safeTimeValue(value: Date | string | null | undefined): number {
  if (value instanceof Date) {
    const time = value.getTime();
    return Number.isNaN(time) ? 0 : time;
  }
  if (typeof value === "string" && value.trim()) {
    const time = new Date(value).getTime();
    return Number.isNaN(time) ? 0 : time;
  }
  return 0;
}

/**
 * Build a summary of recent activities (≤1500 chars) from newest to oldest.
 */
function buildActivitiesSummary(activities: Activity[]): string {
  const sorted = [...activities]
    .filter((a) => !a.isSystem)
    .sort((a, b) => safeTimeValue(b.activityAt) - safeTimeValue(a.activityAt))
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
  aiEntries?: DealAiEntries | null,
  graphContext?: GraphContextResponse | null,
): string {
  const previousBriefings = (aiEntries?.briefings ?? []).slice(0, 3).map((briefing) => ({
    title:
      ((briefing.metadata as BriefingMetadata | undefined)?.title?.trim()) ||
      `會議準備 ${new Date(briefing.createdAt).toLocaleDateString("zh-TW")}`,
    created_at: briefing.createdAt,
    content_excerpt: briefing.content.slice(0, 240),
  }));
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
    previous_briefings_count: aiEntries?.briefings.length ?? 0,
    ...(previousBriefings.length > 0 ? { previous_briefings: previousBriefings } : {}),
    ...(debriefInsights !== undefined ? { debrief_insights: debriefInsights } : {}),
    suggested_skill: "/crm-briefing",
  };

  const sanitized = sanitizeContextValue(contextPack);
  let packed = JSON.stringify(sanitized, null, 2);
  if (packed.length > 2000) {
    // Truncate activities_summary to fit
    const truncatedPack = { ...(sanitized as Record<string, unknown>), activities_summary: "（摘要過長，已截斷）" };
    packed = JSON.stringify(truncatedPack, null, 2);
  }

  return buildCrmKnowledgePrompt({
    promptLabel: "/crm-briefing",
    baseContext: JSON.parse(packed),
    graphContext: graphContext || null,
  });
}

function normalizeSavedChatHistory(
  metadata: Record<string, unknown> | undefined,
  fallbackContent: string
): ChatMessage[] {
  const rawHistory = metadata?.chat_history;
  if (Array.isArray(rawHistory)) {
    const parsed = rawHistory
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const role = (item as Record<string, unknown>).role;
        const content = (item as Record<string, unknown>).content;
        if (
          (role === "user" || role === "assistant") &&
          typeof content === "string" &&
          content.trim()
        ) {
          return { role, content };
        }
        return null;
      })
      .filter((item): item is ChatMessage => item !== null);
    if (parsed.length > 0) {
      return parsed;
    }
  }

  if (fallbackContent.trim()) {
    return [{ role: "assistant", content: fallbackContent }];
  }

  return [];
}

function buildResumeBriefingPrompt(
  deal: Deal,
  activities: Activity[],
  company: Company | null,
  contacts: Contact[],
  aiEntries: DealAiEntries | null | undefined,
  briefing: AiInsight | null,
  chatHistory: ChatMessage[],
  message: string,
  graphContext?: GraphContextResponse | null,
): string {
  const baseContext = {
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
      amount_twd: deal.amountTwd ?? null,
    },
    activities_summary: buildActivitiesSummary(activities),
    contacts: contacts.map((c) => ({ name: c.name, title: c.title ?? null })),
    previous_briefings_count: aiEntries?.briefings.length ?? 0,
  };

  const transcript = chatHistory
    .slice(-12)
    .map((entry) => `${entry.role === "user" ? "使用者" : "AI"}：${entry.content}`)
    .join("\n\n");

  const savedTitle =
    ((briefing?.metadata as BriefingMetadata | undefined)?.title?.trim()) ||
    (briefing ? `會議準備 ${new Date(briefing.createdAt).toLocaleDateString("zh-TW")}` : "未命名 briefing");

  const packed = JSON.stringify(sanitizeContextValue(baseContext), null, 2);

  return buildCrmKnowledgePrompt({
    promptLabel: "/crm-briefing",
    baseContext: {
      ...JSON.parse(packed),
      saved_briefing_title: savedTitle,
      latest_summary: briefing?.content ?? "",
      transcript: transcript || "（無）",
    },
    graphContext: graphContext || null,
    userMessage: message,
    followUp: true,
  });
}

function buildBriefingTitle(createdAtIso?: string): string {
  const date = createdAtIso ? new Date(createdAtIso) : new Date();
  return `會議準備 ${date.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })}`;
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
 * Looks for ## LINE 和 ## Email (or similar headings).
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

// ─── CopyButton ──────────────────────────────────────────────────────────────

function CopyButton({ text, className = "" }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const t = useInk("light");

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
    <span className={className}>
      <Btn
        t={t}
        size="sm"
        variant="outline"
        onClick={handleCopy}
        icon={copied ? <Check className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />}
      >
      {copied ? (
        <>
          已複製
        </>
      ) : (
        <>
          複製
        </>
      )}
      </Btn>
    </span>
  );
}

// ─── FollowUpDraftUI ─────────────────────────────────────────────────────────

function FollowUpDraftUI({ draft }: { draft: FollowUpDraft }) {
  const t = useInk("light");
  const [activeTab, setActiveTab] = useState<"line" | "email">("line");
  const [lineText, setLineText] = useState(draft.line);
  const [emailSubject, setEmailSubject] = useState(draft.email.subject);
  const [emailBody, setEmailBody] = useState(draft.email.body);

  return (
    <div style={{ border: `1px solid ${t.c.inkHair}`, borderRadius: 2, background: t.c.surface, padding: 12 }}>
      <Tabs
        t={t}
        value={activeTab}
        onChange={setActiveTab}
        variant="underline"
        items={[
          { value: "line", label: "LINE" },
          { value: "email", label: "Email" },
        ]}
        panels={{
          line: (
            <div className="space-y-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-dim">LINE 訊息草稿</span>
              <CopyButton text={lineText} />
            </div>
            <Textarea
              t={t}
              value={lineText}
              onChange={setLineText}
              rows={6}
              resize="none"
              fontVariant="mono"
            />
            </div>
          ),
          email: (
            <div className="space-y-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-dim">Email 草稿</span>
              <CopyButton text={`主旨：${emailSubject}\n\n${emailBody}`} />
            </div>
            <div className="space-y-2">
              <div>
                <label className="block text-xs text-dim mb-1">主旨</label>
                <Input
                  t={t}
                  value={emailSubject}
                  onChange={setEmailSubject}
                />
              </div>
              <div>
                <label className="block text-xs text-dim mb-1">正文</label>
                <Textarea
                  t={t}
                  value={emailBody}
                  onChange={setEmailBody}
                  rows={8}
                  resize="none"
                />
              </div>
            </div>
            </div>
          ),
        }}
      />
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
        className="px-4 py-2 text-sm rounded-lg bg-accent-soft text-primary border border-primary/30 hover:bg-accent-soft transition-colors disabled:opacity-50"
      >
        {advancing ? "更新中..." : `推進到「${nextStage}」`}
      </button>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

// ─── CrmAiPanel ──────────────────────────────────────────────────────────────

const MAX_TURNS = COWORK_MAX_TURNS;

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
  initialBriefing,
  onBriefingSaved,
}: CrmAiPanelProps) {
  const { partner } = useAuth();
  const workspaceId = resolveCopilotWorkspaceId(partner);
  const t = useInk("light");
  const { c, fontBody, fontHead, fontMono } = t;
  const [status, setStatus] = useState<AiStatus>("idle");
  const [streamingText, setStreamingText] = useState("");
  const [finalText, setFinalText] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [followUp, setFollowUp] = useState<FollowUpDraft | null>(null);
  const [helperOffline, setHelperOffline] = useState(false);
  const [helperChecking, setHelperChecking] = useState(false);
  const [capability, setCapability] = useState<CoworkCapabilityCheck | null>(null);
  const [permissionLabel, setPermissionLabel] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [helperEvents, setHelperEvents] = useState<string[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [graphContext, setGraphContext] = useState<GraphContextResponse | null>(null);
  const graphContextRef = useRef<GraphContextResponse | null>(null);
  const [graphContextUnavailableReason, setGraphContextUnavailableReason] = useState<string | null>(null);

  // Briefing chat state
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [userInput, setUserInput] = useState("");
  const [turnCount, setTurnCount] = useState(0);
  const [activeBriefing, setActiveBriefing] = useState<AiInsight | null>(
    initialBriefing ?? null
  );
  const [briefingSaveError, setBriefingSaveError] = useState<string | null>(null);
  const [briefingSaving, setBriefingSaving] = useState(false);
  const [savingAsNew, setSavingAsNew] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const conversationKey = `crm.${workspaceId || "default"}.${mode}.${deal.id}`;
  const startedStorageKey = `zenos.copilot.started.${conversationKey}`;
  const snapshotStorageKey = `zenos.copilot.snapshot.${conversationKey}`;
  const conversationId = useRef(`crm-${workspaceId || "default"}-${mode}-${deal.id}`);
  const hasStartedConversation = useRef(false);
  const hasAutoStarted = useRef(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const chatHistoryRef = useRef<ChatMessage[]>([]);
  const turnCountRef = useRef(0);
  const activeBriefingRef = useRef<AiInsight | null>(initialBriefing ?? null);

  const title = mode === "briefing" ? "AI 會議準備" : "AI 活動 Debrief";
  const connectorStatus = helperChecking ? "checking" : helperOffline ? "disconnected" : "connected";
  const shellChatStatus =
    permissionLabel
      ? "awaiting-local-approval"
      : status === "loading"
        ? "loading"
        : status === "streaming"
          ? "streaming"
          : status === "error"
            ? "error"
            : "idle";
  const railEntry = {
    intent_id: mode === "briefing" ? "crm.briefing" : "crm.debrief",
    title,
    mode: "artifact" as const,
    launch_behavior: "auto_start" as const,
    session_policy: "scoped_resume" as const,
    suggested_skill: mode === "briefing" ? "/crm-briefing" : "/crm-debrief",
    claude_code_bootstrap: {
      use_project_claude_config: true,
      required_skills: [
        mode === "briefing" ? "/crm-briefing" : "/crm-debrief",
        "/zenos-governance",
        "skills/governance/task-governance.md",
        "skills/governance/document-governance.md",
      ],
      governance_topics: ["task", "document"],
      verify_zenos_write: true,
      execution_contract: [
        "Use the deal workspace .claude MCP/settings files and do not assume a global helper session has the right tenant key.",
        "Before any governed task or document write, load ZenOS task/document governance and call mcp__zenos__governance_guide.",
        "For any ordered multi-step follow-up, create a real plan first and attach tasks with plan_id and plan_order instead of using parent tasks as a fake plan.",
        "Do not report CRM follow-up tasks or notes as created until ZenOS returns ids and you re-read them successfully.",
      ],
    },
    scope: {
      workspace_id: workspaceId,
      deal_id: deal.id,
      entity_ids: [deal.id],
      scope_label: `${deal.title} / ${mode === "briefing" ? "會議準備" : "活動 debrief"}`,
    },
    context_pack: {
      mode,
      deal_id: deal.id,
      graph_context: graphContext,
    },
    get_context_pack: () => ({
      mode,
      deal_id: deal.id,
      graph_context: graphContextRef.current,
    }),
    build_prompt: () =>
      mode === "briefing"
        ? buildBriefingPrompt(deal, activities, company, contacts, aiEntries, graphContextRef.current)
        : triggerActivity
          ? buildDebriefPrompt(deal, company, triggerActivity, aiEntries)
          : "",
  };

  const lightFieldVars: CSSProperties = {
    "--primary": c.vermillion,
    "--foreground": c.ink,
    "--field-bg": c.surfaceHi,
    "--field-bg-hover": c.surface,
    "--field-border": c.inkHairBold,
    "--field-border-strong": c.vermLine,
    "--focus-ring": "rgba(182, 58, 44, 0.12)",
    "--focus-outline": "rgba(182, 58, 44, 0.42)",
    colorScheme: "light",
  } as CSSProperties;

  const replaceChatHistory = useCallback((messages: ChatMessage[]) => {
    chatHistoryRef.current = messages;
    setChatHistory(messages);
  }, []);

  const appendChatMessage = useCallback((message: ChatMessage) => {
    const next = [...chatHistoryRef.current, message];
    chatHistoryRef.current = next;
    setChatHistory(next);
  }, []);

  const setTurnCountValue = useCallback((value: number) => {
    turnCountRef.current = value;
    setTurnCount(value);
  }, []);

  const appendHelperEvent = useCallback((message: string) => {
    const nextLine = message.trim();
    if (!nextLine) return;
    setHelperEvents((prev) => {
      if (prev[prev.length - 1] === nextLine) return prev;
      return [...prev, nextLine].slice(-6);
    });
  }, []);

  const ensureGraphContext = useCallback(async (): Promise<GraphContextResponse | null> => {
    if (mode !== "briefing" || !company?.zenosEntityId) {
      graphContextRef.current = null;
      setGraphContext(null);
      setGraphContextUnavailableReason(null);
      return null;
    }
    if (capability && !capability.mcpOk) {
      graphContextRef.current = null;
      setGraphContext(null);
      setGraphContextUnavailableReason(graphContextUnavailableNotice());
      return null;
    }
    const nextGraphContext = await fetchGraphContext(token, { seedId: company.zenosEntityId });
    graphContextRef.current = nextGraphContext;
    setGraphContext(nextGraphContext);
    setGraphContextUnavailableReason(nextGraphContext ? null : graphContextUnavailableNotice());
    return nextGraphContext;
  }, [capability, company?.zenosEntityId, mode, token]);

  useEffect(() => {
    activeBriefingRef.current = activeBriefing;
  }, [activeBriefing]);

  useEffect(() => {
    if (capability && !capability.mcpOk) {
      graphContextRef.current = null;
      setGraphContext(null);
      setGraphContextUnavailableReason(graphContextUnavailableNotice());
    }
  }, [capability]);

  useEffect(() => {
    const hasState =
      chatHistory.length > 0 ||
      Boolean(streamingText) ||
      Boolean(finalText) ||
      Boolean(errorMsg) ||
      Boolean(followUp) ||
      Boolean(permissionLabel) ||
      helperEvents.length > 0 ||
      turnCount > 0 ||
      Boolean(userInput) ||
      hasStartedConversation.current;

    if (!hasState) {
      clearSessionSnapshot(snapshotStorageKey);
      return;
    }

    writeSessionSnapshot<CrmCopilotSnapshot>(snapshotStorageKey, {
      status,
      streamingText,
      finalText,
      errorMsg,
      followUp,
      permissionLabel,
      helperEvents,
      chatHistory,
      turnCount,
      requestId,
      userInput,
    });
  }, [
    chatHistory,
    errorMsg,
    finalText,
    followUp,
    helperEvents,
    permissionLabel,
    requestId,
    snapshotStorageKey,
    status,
    streamingText,
    turnCount,
    userInput,
  ]);

  const persistBriefingSnapshot = useCallback(
    async (content: string, saveMode: "upsert" | "clone" = "upsert") => {
      if (mode !== "briefing" || !content.trim() || !token) return null;

      const existing = saveMode === "upsert" ? activeBriefingRef.current : null;
      const existingMeta = (existing?.metadata as BriefingMetadata | undefined) ?? {};
      const metadata: BriefingMetadata = {
        ...existingMeta,
        title: existingMeta.title || buildBriefingTitle(existing?.createdAt),
        conversation_id: conversationId.current,
        turn_count: turnCountRef.current,
        chat_history: chatHistoryRef.current,
        saved_at: new Date().toISOString(),
        ...(graphContextRef.current
          ? {
              graph_context_seed: graphContextRef.current.seed.id,
              graph_context_l2_count: graphContextRef.current.neighbors.length,
              graph_context_l3_count: graphContextRef.current.neighbors.reduce(
                (sum, neighbor) => sum + neighbor.documents.length,
                0
              ),
            }
          : {}),
      };

      setBriefingSaveError(null);
      if (saveMode === "clone") {
        setSavingAsNew(true);
      } else {
        setBriefingSaving(true);
      }

      try {
        const saved =
          existing && saveMode === "upsert"
            ? await updateBriefing(token, existing.id, {
                content,
                metadata: metadata as Record<string, unknown>,
              })
            : await createAiInsight(token, deal.id, {
                insightType: "briefing",
                content,
                metadata: metadata as Record<string, unknown>,
              });
        setActiveBriefing(saved);
        activeBriefingRef.current = saved;
        onBriefingSaved?.(saved, existing && saveMode === "upsert" ? "update" : "create");
        return saved;
      } catch (err) {
        setBriefingSaveError(err instanceof Error ? err.message : "儲存 briefing 失敗");
        return null;
      } finally {
        setBriefingSaving(false);
        setSavingAsNew(false);
      }
    },
    [deal.id, mode, onBriefingSaved, token]
  );

  /**
   * Core streaming function.
   * @param prompt — the prompt to send; if omitted, builds the briefing prompt.
   * @param isFollowUp — if true, append AI response to chatHistory on completion.
   */
  const startStream = useCallback(async (
    prompt?: string,
    isFollowUp = false,
    fallbackStartPrompt?: string
  ) => {
    const baseUrl = getDefaultHelperBaseUrl();
    const helperToken = getDefaultHelperToken();
    const model = getDefaultHelperModel();
    const cwd = getDefaultHelperCwd();

    // Health check before streaming
    setHelperChecking(true);
    const health = await checkCoworkHelperHealth(
      baseUrl,
      helperToken || undefined,
      workspaceId
    );
    setHelperChecking(false);
    if (!health.ok) {
      setHelperOffline(true);
      setCapability(null);
      setStatus("idle");
      return;
    }
    setHelperOffline(false);
    setCapability(health.capability || null);
    setPermissionLabel(null);
    setHelperEvents([]);

    const resolvedPrompt =
      prompt ??
      (mode === "briefing"
        ? buildBriefingPrompt(
            deal,
            activities,
            company,
            contacts,
            aiEntries,
            await ensureGraphContext()
          )
        : triggerActivity
          ? buildDebriefPrompt(deal, company, triggerActivity, aiEntries)
          : null);

    if (!resolvedPrompt) return;

    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setStreamingText("");
    setRequestId(null);
    if (!isFollowUp) {
      setFinalText("");
      setErrorMsg(null);
      setFollowUp(null);
      setCollapsed(false);
    } else {
      setErrorMsg(null);
    }

    const runOnce = async (
      streamMode: "start" | "continue",
      promptToSend: string
    ) => {
      let collected = "";
      let stderrCombined = "";
      let exitCode: number | null = null;

      await streamCoworkChat({
        baseUrl,
        token: helperToken || undefined,
        mode: streamMode,
        conversationId: conversationId.current,
        prompt: promptToSend,
        model: model || undefined,
        cwd: cwd || undefined,
        maxTurns: COWORK_MAX_TURNS,
        signal: controller.signal,
        onEvent: (event: CoworkStreamEvent) => {
          if ("requestId" in event && event.requestId) {
            setRequestId(event.requestId);
          }
          if (event.type === "capability_check") {
            setCapability(event.capability);
            if (!event.capability.mcpOk) {
              appendHelperEvent("ZenOS 連線失敗，這輪僅能讀取當前上下文。");
            }
            const missingSkills = event.capability.missingSkills || [];
            if (missingSkills.length > 0) {
              appendHelperEvent(`缺少 skill：${missingSkills.join(", ")}`);
            }
            return;
          }
          if (event.type === "permission_request") {
            const toolLabel = event.request?.toolName || "工具";
            setPermissionLabel(`等待本機確認：${toolLabel}`);
            appendHelperEvent(`等待本機確認 ${toolLabel}（${event.request?.timeoutSeconds || 30} 秒）`);
            return;
          }
          if (event.type === "permission_result") {
            const toolLabel = event.result?.toolName || "工具";
            const approved = event.result?.approved;
            setPermissionLabel(approved ? null : `授權被拒：${toolLabel}`);
            appendHelperEvent(
              `${toolLabel} ${approved ? "已核准" : `已拒絕（${event.result?.reason || "unknown"}）`}`
            );
            return;
          }
          if (event.type === "message") {
            setPermissionLabel(null);
            setStatus("streaming");
            const { delta, debug } = parseStreamLine(event.line);
            if (debug) {
              appendHelperEvent(debug);
            }
            if (delta) {
              collected += delta;
              setStreamingText(collected);
            }
          } else if (event.type === "stderr") {
            const text = event.text.trim();
            if (text) {
              stderrCombined += `${stderrCombined ? "\n" : ""}${text}`;
            }
          } else if (event.type === "done") {
            setPermissionLabel(null);
            if (typeof event.code === "number") {
              exitCode = event.code;
            }
            const text = collected.trim();
            setStreamingText("");

            if (mode === "briefing") {
              // Append AI response to chat history; stay "idle" so user can follow up
              if (text) {
                appendChatMessage({ role: "assistant", content: text });
              }
              setFinalText(text);
              setStatus("idle");
            } else {
              // Debrief mode — original behaviour; set "done" to show follow-up draft
              setFinalText(text);
              if (text) {
                const draft = extractFollowUpDraft(text);
                if (draft) setFollowUp(draft);
                onStreamComplete?.(text);
              }
              setStatus("done");
            }
          } else if (event.type === "error") {
            setErrorMsg(event.message);
            setPermissionLabel(null);
            setStatus("error");
            appendHelperEvent(event.message);
          }
        },
      });

      if (exitCode !== null && exitCode !== 0) {
        throw new Error(stderrCombined || `Claude Code CLI exited with code ${exitCode}`);
      }

      return collected.trim();
    };

    try {
      const preferredMode =
        mode === "briefing" && hasStartedConversation.current ? "continue" : "start";
      let completedText = "";

      if (preferredMode === "continue") {
        try {
          completedText = await runOnce("continue", resolvedPrompt);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          if (/not found|session/i.test(msg)) {
            hasStartedConversation.current = false;
            clearSessionStarted(startedStorageKey);
            completedText = await runOnce(
              "start",
              fallbackStartPrompt ?? resolvedPrompt
            );
          } else {
            throw err;
          }
        }
      } else {
        completedText = await runOnce("start", resolvedPrompt);
      }

      hasStartedConversation.current = true;
      markSessionStarted(startedStorageKey);
      if (mode === "briefing" && completedText) {
        await persistBriefingSnapshot(completedText);
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setRequestId(null);
        setStatus("idle");
        return;
      }
      setErrorMsg(err instanceof Error ? err.message : "串流失敗");
      setStatus("error");
    } finally {
      setHelperChecking(false);
    }
  }, [
    mode,
    deal,
    activities,
    company,
    contacts,
    triggerActivity,
    onStreamComplete,
    aiEntries,
    appendChatMessage,
    appendHelperEvent,
    persistBriefingSnapshot,
  ]);

  useEffect(() => {
    abortRef.current?.abort();
    conversationId.current = `crm-${workspaceId || "default"}-${mode}-${deal.id}`;
    hasStartedConversation.current = Boolean(readFreshSessionStartedAt(startedStorageKey));
    setBriefingSaveError(null);
    setUserInput("");
    setStreamingText("");
    setFollowUp(null);
    setCollapsed(false);
    graphContextRef.current = null;
    setGraphContext(null);
    setGraphContextUnavailableReason(null);
    setHelperEvents([]);
    setPermissionLabel(null);
    setErrorMsg(null);
    setRequestId(null);

    const snapshot = readFreshSessionSnapshot<CrmCopilotSnapshot>(snapshotStorageKey);
    if (snapshot) {
      if (mode === "briefing" && initialBriefing) {
        setActiveBriefing(initialBriefing);
        activeBriefingRef.current = initialBriefing;
      }
      replaceChatHistory(snapshot.chatHistory ?? []);
      setTurnCountValue(snapshot.turnCount ?? 0);
      setFinalText(snapshot.finalText ?? "");
      setStreamingText(snapshot.streamingText ?? "");
      setStatus(
        snapshot.status === "loading" || snapshot.status === "streaming"
          ? "idle"
          : snapshot.status ?? "idle"
      );
      setErrorMsg(snapshot.errorMsg ?? null);
      setFollowUp(snapshot.followUp ?? null);
      setPermissionLabel(snapshot.permissionLabel ?? null);
      setHelperEvents(snapshot.helperEvents ?? []);
      setRequestId(snapshot.requestId ?? null);
      setUserInput(snapshot.userInput ?? "");
      hasAutoStarted.current = true;
      return;
    }

    if (mode !== "briefing") {
      replaceChatHistory([]);
      setTurnCountValue(0);
      setFinalText("");
      setStatus("idle");
      hasAutoStarted.current = false;
      return;
    }

    if (initialBriefing) {
      const metadata = (initialBriefing.metadata as BriefingMetadata | undefined) ?? {};
      const restoredHistory = normalizeSavedChatHistory(
        initialBriefing.metadata as Record<string, unknown>,
        initialBriefing.content
      );
      setActiveBriefing(initialBriefing);
      activeBriefingRef.current = initialBriefing;
      replaceChatHistory(restoredHistory);
      setTurnCountValue(
        typeof metadata.turn_count === "number"
          ? metadata.turn_count
          : restoredHistory.filter((entry) => entry.role === "user").length
      );
      setFinalText(initialBriefing.content);
      setStatus("idle");
      hasAutoStarted.current = true;
      return;
    }

    setActiveBriefing(null);
    activeBriefingRef.current = null;
    replaceChatHistory([]);
    setTurnCountValue(0);
    setFinalText("");
    setStatus("idle");
    hasAutoStarted.current = false;
  }, [
    deal.id,
    initialBriefing,
    mode,
    replaceChatHistory,
    setTurnCountValue,
    snapshotStorageKey,
    startedStorageKey,
    workspaceId,
  ]);

  // Auto-start briefing/debrief on mount so opening the panel immediately does work.
  useEffect(() => {
    if (!hasAutoStarted.current) {
      if (mode === "briefing" && !initialBriefing) {
        hasAutoStarted.current = true;
        void startStream();
      } else if (mode === "debrief" && triggerActivity) {
        hasAutoStarted.current = true;
        void startStream();
      }
    }
    return () => {
      abortRef.current?.abort();
    };
  }, [initialBriefing, mode, triggerActivity, startStream]);

  // Auto-scroll to bottom when chat history updates
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, streamingText]);

  function handleCancel() {
    if (requestId || conversationId.current) {
      void Promise.resolve(
        cancelCoworkRequest({
          baseUrl: getDefaultHelperBaseUrl(),
          token: getDefaultHelperToken() || undefined,
          requestId: requestId || undefined,
          conversationId: conversationId.current,
        })
      ).catch(() => undefined);
    }
    abortRef.current?.abort();
    setPermissionLabel(null);
    setRequestId(null);
    setStatus("idle");
  }

  async function handleSendMessage(overrideInput?: string) {
    const message = (overrideInput ?? userInput).trim();
    if (!message || status !== "idle") return;
    setUserInput("");
    appendChatMessage({ role: "user", content: message });
    setTurnCountValue(turnCountRef.current + 1);

    const resumePrompt = buildResumeBriefingPrompt(
      deal,
      activities,
      company,
      contacts,
      aiEntries,
      activeBriefingRef.current,
      chatHistoryRef.current,
      message,
      graphContextRef.current
    );

    await startStream(
      hasStartedConversation.current ? resumePrompt : resumePrompt,
      true,
      resumePrompt
    );
  }

  async function handleSaveAsNewBriefing() {
    const latestAssistant = [...chatHistoryRef.current]
      .reverse()
      .find((entry) => entry.role === "assistant" && entry.content.trim());
    const contentToSave = latestAssistant?.content ?? finalText;
    if (!contentToSave.trim()) return;
    await persistBriefingSnapshot(contentToSave, "clone");
  }

  const displayText = status === "streaming" ? streamingText : finalText;
  const showInlineProgress =
    chatHistory.length === 0 &&
    !streamingText.trim() &&
    (status === "loading" || status === "streaming");
  const showDebriefProgress =
    mode === "debrief" &&
    !displayText.trim() &&
    (status === "loading" || status === "streaming");
  const progressTitle =
    permissionLabel ||
    (helperChecking
      ? "檢查 Local Helper…"
      : status === "loading"
        ? "正在整理 CRM 與知識圖譜內容…"
        : "Claude 已開始回應，等待首段內容…");
  const viewportMessages = useMemo(
    () => chatHistory.map((msg, index) => ({ ...msg, timestamp: index + 1 })),
    [chatHistory]
  );

  return (
    <CopilotRailShell
      open
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose?.();
      }}
      entry={railEntry}
      chatStatus={shellChatStatus}
      connectorStatus={connectorStatus}
      diagnostics={
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px]">
          <div className="flex flex-wrap items-center gap-2">
            {mode === "briefing" && activeBriefing && (
              <span className="rounded-full border bd-hair px-2 py-0.5 text-[10px] text-dim">
                {((activeBriefing.metadata as BriefingMetadata | undefined)?.title?.trim()) ||
                  buildBriefingTitle(activeBriefing.createdAt)}
              </span>
            )}
            {mode === "briefing" && activeBriefing && status === "idle" && !briefingSaveError && (
              <span className="text-xs" style={{ color: c.jade }}>已存成 briefing</span>
            )}
            {permissionLabel && (
              <span
                className="rounded-full px-2 py-0.5 text-[10px]"
                style={{
                  border: `1px solid ${c.vermLine}`,
                  background: c.vermSoft,
                  color: c.vermillion,
                }}
              >
                {permissionLabel}
              </span>
            )}
            {capability && !capability.mcpOk && (
              <span
                className="rounded-full px-2 py-0.5 text-[10px]"
                style={{
                  border: `1px solid ${c.vermLine}`,
                  background: c.vermSoft,
                  color: c.vermillion,
                }}
              >
                ZenOS 連線失敗
              </span>
            )}
            {capability?.missingSkills?.map((skill) => (
              <span
                key={skill}
                className="rounded-full px-2 py-0.5 text-[10px]"
                style={{
                  border: `1px solid ${c.vermLine}`,
                  background: c.vermSoft,
                  color: c.vermillion,
                }}
              >
                缺 skill：{skill}
              </span>
            ))}
          </div>
          {(status === "done" || status === "error" || (mode === "briefing" && chatHistory.length > 0)) && (
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="rounded p-1 text-dim transition-colors hover:bg-soft hover:text-foreground"
              aria-label={collapsed ? "展開" : "收合"}
            >
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
          )}
        </div>
      }
    >
      {!collapsed && (
        <div style={lightFieldVars}>
          {/* ── Helper offline fallback (both modes) ── */}
          {helperOffline && status === "idle" && (
            <div
              className="m-4 flex items-start gap-2 p-3"
              style={{
                borderRadius: 16,
                border: `1px solid ${c.vermLine}`,
                background: c.vermSoft,
              }}
            >
              <PlugZap className="mt-0.5 h-4 w-4 shrink-0" style={{ color: c.vermillion }} />
              <div className="text-sm" style={{ color: c.ink }}>
                <p className="font-medium">Local Helper 未連線</p>
                <p className="mt-0.5 text-xs" style={{ color: c.inkMuted }}>
                  請先啟動 Local Helper（port 4317），再重試。
                </p>
              </div>
              <button
                onClick={() => startStream()}
                className="ml-auto shrink-0 rounded-lg px-3 py-1 text-xs transition-colors"
                style={{
                  border: `1px solid ${c.vermLine}`,
                  background: c.surface,
                  color: c.vermillion,
                }}
              >
                重試
              </button>
            </div>
          )}

          {mode === "briefing" ? (
            /* ══ Briefing: conversational UI ══ */
            <div className="flex flex-col">
              <div className="px-4 pt-4">
                <GraphContextBadge
                  graphContext={graphContext}
                  unavailableReason={graphContextUnavailableReason}
                />
              </div>
              {briefingSaveError && (
                <div
                  className="mx-4 mt-4 px-3 py-2 text-xs"
                  style={{
                    borderRadius: 2,
                    border: `1px solid ${c.vermLine}`,
                    background: c.vermSoft,
                    color: c.vermillion,
                  }}
                >
                  {briefingSaveError}
                </div>
              )}

              {mode === "briefing" && chatHistory.length > 0 && (
                <div className="px-4 pt-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => void handleSaveAsNewBriefing()}
                      disabled={savingAsNew || briefingSaving || status === "streaming" || status === "loading"}
                      className="px-3 py-1.5 text-xs rounded-lg border bd-hair text-dim hover:text-foreground hover:border-foreground/30 transition-colors disabled:opacity-50"
                    >
                      {savingAsNew ? "另存中..." : "另存新 briefing"}
                    </button>
                    {briefingSaving && (
                      <span className="text-xs text-dim">儲存中...</span>
                    )}
                  </div>
                </div>
              )}

              {/* Chat history — scrollable */}
              {chatHistory.length > 0 && (
                <div className="p-4">
                  <CopilotChatViewport
                    messages={viewportMessages}
                    streamingText={status === "loading" ? progressTitle : streamingText}
                    isStreaming={status === "streaming" || status === "loading"}
                    emptyStateTitle="CRM 助手已啟動"
                    emptyStateDescription="可以直接追問會議重點、下一步或草稿調整。"
                  />
                  <div ref={chatEndRef} />
                </div>
              )}

              {showInlineProgress && (
                <div className="p-4">
                  <div
                    style={{
                      borderRadius: 18,
                      border: `1px solid ${c.inkHair}`,
                      background: c.surface,
                      padding: 16,
                    }}
                  >
                    <div className="flex items-center gap-2" style={{ color: c.inkMuted }}>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span style={{ fontFamily: fontHead, fontSize: 14, color: c.ink }}>
                        {progressTitle}
                      </span>
                    </div>
                    <p
                      style={{
                        marginTop: 8,
                        fontSize: 12,
                        color: c.inkMuted,
                        lineHeight: 1.6,
                      }}
                    >
                      helper 已啟動，這一輪會先整理最近活動、briefing 與知識圖譜，再輸出會議摘要。
                    </p>
                    {helperEvents.length > 0 && (
                      <div
                        style={{
                          marginTop: 12,
                          borderTop: `1px solid ${c.inkHair}`,
                          paddingTop: 12,
                          display: "grid",
                          gap: 6,
                        }}
                      >
                        {helperEvents.slice(-3).map((line, index) => (
                          <div key={`${index}-${line}`} style={{ fontSize: 11, color: c.inkMuted }}>
                            {line}
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-4 flex justify-end">
                      <button
                        onClick={handleCancel}
                        className="rounded-lg px-3 py-1 text-xs transition-colors"
                        style={{
                          border: `1px solid ${c.inkHairBold}`,
                          background: c.paperWarm,
                          color: c.inkMuted,
                        }}
                      >
                        取消
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Streaming first response (no history yet) */}
              {status === "streaming" && chatHistory.length === 0 && streamingText && (
                <div className="p-4">
                  <span className="text-xs text-dim">Claude</span>
                  <div
                    className="mt-1 rounded-zen p-3 text-sm"
                    style={{
                      background: c.surface,
                      border: `1px solid ${c.inkHair}`,
                    }}
                  >
                    <MarkdownRenderer content={streamingText} className="text-sm text-foreground space-y-1" />
                  </div>
                </div>
              )}

              {/* Cancel button while streaming */}
              {status === "streaming" && !showInlineProgress && (
                <div className="flex justify-end px-4 pb-2">
                  <button
                    onClick={handleCancel}
                    className="px-3 py-1 text-xs rounded-lg text-dim hover:text-foreground border bd-hair hover:border-foreground/30 transition-colors"
                  >
                    取消
                  </button>
                </div>
              )}

              {/* Error */}
              {status === "error" && (
                <div className="p-4 space-y-2">
                  <p className="text-sm text-red-400">{errorMsg ?? "發生錯誤"}</p>
                  <button
                    onClick={() => startStream()}
                    className="px-4 py-1.5 text-xs rounded-lg bg-soft text-foreground hover:bg-soft transition-colors flex items-center gap-1.5"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重試
                  </button>
                </div>
              )}

              {/* Input area — show after first response, while under turn limit */}
              {status !== "streaming" && status !== "loading" && chatHistory.length > 0 && turnCount < MAX_TURNS && (
                <div className="border-t bd-hair p-3 space-y-2">
                  <CopilotInputBar
                    status="idle"
                    value={userInput}
                    onValueChange={setUserInput}
                    onSend={(input) => void handleSendMessage(input)}
                    onCancel={() => void handleCancel()}
                    onRetry={() => void startStream()}
                    hasStructuredResult={false}
                    placeholder="追問或調整重點..."
                    sendOnPlainEnter={false}
                  />
                  <p className="text-xs text-dim">
                    `Enter` 換行，`Cmd/Ctrl + Enter` 送出
                  </p>
                </div>
              )}

              {/* Turn limit reached */}
              {turnCount >= MAX_TURNS && (
                <div className="border-t bd-hair p-3 text-sm text-dim text-center">
                  已達對話上限（{MAX_TURNS} 輪）。如需繼續，請關閉後重新開啟。
                </div>
              )}

              {/* Copy latest summary button */}
              {chatHistory.length > 0 && status === "idle" && (
                <div className="px-3 pb-3">
                  <button
                    onClick={() => {
                      const lastAssistant = [...chatHistory].reverse().find((m) => m.role === "assistant");
                      if (lastAssistant) {
                        void navigator.clipboard.writeText(lastAssistant.content);
                      }
                    }}
                    className="w-full py-2 text-sm border bd-hair rounded-md hover:bg-soft transition-colors text-dim"
                    style={{
                      background: c.surface,
                      borderColor: c.inkHairBold,
                      color: c.inkMuted,
                    }}
                  >
                    複製最新準備摘要
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* ══ Debrief: original single-shot UI ══ */
            <div className="p-4 space-y-4">
              {showDebriefProgress && (
                <div
                  style={{
                    borderRadius: 18,
                    border: `1px solid ${c.inkHair}`,
                    background: c.surface,
                    padding: 16,
                  }}
                >
                  <div className="flex items-center gap-2" style={{ color: c.inkMuted }}>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span style={{ fontFamily: fontHead, fontSize: 14, color: c.ink }}>
                      {progressTitle}
                    </span>
                  </div>
                  <p
                    style={{
                      marginTop: 8,
                      fontSize: 12,
                      color: c.inkMuted,
                      lineHeight: 1.6,
                    }}
                  >
                    helper 已啟動，這一輪會先整理本次活動、既有 briefing 與承諾事項，再輸出 debrief。
                  </p>
                  {helperEvents.length > 0 && (
                    <div
                      style={{
                        marginTop: 12,
                        borderTop: `1px solid ${c.inkHair}`,
                        paddingTop: 12,
                        display: "grid",
                        gap: 6,
                      }}
                    >
                      {helperEvents.slice(-3).map((line, index) => (
                        <div key={`${index}-${line}`} style={{ fontSize: 11, color: c.inkMuted }}>
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-4 flex justify-end">
                    <button
                      onClick={handleCancel}
                      className="rounded-lg px-3 py-1 text-xs transition-colors"
                      style={{
                        border: `1px solid ${c.inkHairBold}`,
                        background: c.paperWarm,
                        color: c.inkMuted,
                      }}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}

              {/* Streaming / done markdown */}
              {(status === "streaming" || status === "done") && displayText && (
                <div className="prose-sm">
                  <MarkdownRenderer
                    content={displayText}
                    className="text-sm text-foreground space-y-1"
                  />
                  {status === "streaming" && (
                    <div className="flex justify-end mt-2">
                      <button
                        onClick={handleCancel}
                        className="px-3 py-1 text-xs rounded-lg text-dim hover:text-foreground border bd-hair hover:border-foreground/30 transition-colors"
                      >
                        取消
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Error */}
              {status === "error" && (
                <div className="space-y-2">
                  <p className="text-sm text-red-400">{errorMsg ?? "發生錯誤"}</p>
                  <button
                    onClick={() => startStream()}
                    className="px-4 py-1.5 text-xs rounded-lg bg-soft text-foreground hover:bg-soft transition-colors flex items-center gap-1.5"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重試
                  </button>
                </div>
              )}

              {/* Follow-up draft */}
              {status === "done" && followUp && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-dim uppercase tracking-wide">
                    Follow-up 草稿
                  </h4>
                  <FollowUpDraftUI draft={followUp} />
                </div>
              )}

              {/* Stage advance */}
              {status === "done" && onStageAdvanced && (
                <div className="pt-2 border-t bd-hair">
                  <p className="text-xs text-dim mb-2">如 AI 建議推進漏斗階段：</p>
                  <StageAdvanceButton deal={deal} token={token} onAdvanced={onStageAdvanced} />
                </div>
              )}

              {/* Re-run after done */}
              {status === "done" && (
                <div className="flex justify-end">
                  <button
                    onClick={() => startStream()}
                    className="px-3 py-1.5 text-xs rounded-lg text-dim hover:text-foreground border bd-hair hover:border-foreground/30 transition-colors flex items-center gap-1.5"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重新生成
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {helperEvents.length > 0 && !showInlineProgress && (
        <div
          className="mt-4 space-y-1 px-3 py-2"
          style={{
            borderRadius: 16,
            border: `1px solid ${c.inkHair}`,
            background: c.paperWarm,
          }}
        >
          {helperEvents.map((line, index) => (
            <div key={`${index}-${line}`} className="text-[11px]" style={{ color: c.inkMuted }}>
              {line}
            </div>
          ))}
        </div>
      )}
    </CopilotRailShell>
  );
}
