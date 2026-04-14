"use client";

/**
 * CrmAiPanel — AI Briefing and Debrief panel for Deal detail page.
 *
 * Reuses cowork-helper.ts streamCoworkChat() for SSE streaming.
 * No AI logic lives here — only context pack assembly, display, and copy.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Copy, Check, RefreshCw, PlugZap, ChevronDown, ChevronUp } from "lucide-react";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import {
  streamCoworkChat,
  checkCoworkHelperHealth,
  getDefaultHelperBaseUrl,
  getDefaultHelperToken,
  getDefaultHelperModel,
  getDefaultHelperCwd,
  CoworkStreamEvent,
} from "@/lib/cowork-helper";
import { sanitizeContextValue } from "@/config/ai-redaction-rules";
import type { Deal, Activity, Company, Contact, FunnelStage, DealAiEntries } from "@/lib/crm-api";
import { patchDealStage } from "@/lib/crm-api";

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
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Parse a raw SSE line from the helper into a text delta.
 * Mirrors parseCoworkStreamLine from marketing/logic.ts but simplified for CRM.
 */
function parseSseLineForDelta(line: string): string {
  const raw = line.trim();
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const candidates: unknown[] = [
      (parsed.delta as Record<string, unknown> | undefined)?.text,
      (parsed.content_block_delta as Record<string, unknown> | undefined)?.text,
      parsed.text,
      (parsed.content_block as Record<string, unknown> | undefined)?.text,
    ];
    const messageObj = parsed.message as Record<string, unknown> | undefined;
    const messageContent = Array.isArray(messageObj?.content) ? messageObj.content : null;
    if (messageContent && messageContent.length > 0) {
      const first = messageContent[0] as Record<string, unknown>;
      candidates.push(first?.text);
    }
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim().length > 0) {
        return candidate;
      }
    }
    return "";
  } catch {
    return raw;
  }
}

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
    // Truncate activities_summary to fit
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

// ─── CrmAiPanel ──────────────────────────────────────────────────────────────

const MAX_TURNS = 8;

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
  const [status, setStatus] = useState<AiStatus>("idle");
  const [streamingText, setStreamingText] = useState("");
  const [finalText, setFinalText] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [followUp, setFollowUp] = useState<FollowUpDraft | null>(null);
  const [helperOffline, setHelperOffline] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Briefing chat state
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [userInput, setUserInput] = useState("");
  const [turnCount, setTurnCount] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const conversationId = useRef(`crm-${mode}-${deal.id}-${Date.now()}`);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const title = mode === "briefing" ? "AI 會議準備" : "AI 活動 Debrief";

  /**
   * Core streaming function.
   * @param prompt — the prompt to send; if omitted, builds the briefing prompt.
   * @param isFollowUp — if true, append AI response to chatHistory on completion.
   */
  const startStream = useCallback(async (prompt?: string, isFollowUp = false) => {
    const baseUrl = getDefaultHelperBaseUrl();
    const helperToken = getDefaultHelperToken();
    const model = getDefaultHelperModel();
    const cwd = getDefaultHelperCwd();

    // Health check before streaming
    const health = await checkCoworkHelperHealth(baseUrl, helperToken || undefined);
    if (!health.ok) {
      setHelperOffline(true);
      setStatus("idle");
      return;
    }
    setHelperOffline(false);

    const resolvedPrompt =
      prompt ??
      (mode === "briefing"
        ? buildBriefingPrompt(deal, activities, company, contacts, aiEntries)
        : triggerActivity
          ? buildDebriefPrompt(deal, company, triggerActivity, aiEntries)
          : null);

    if (!resolvedPrompt) return;

    abortRef.current = new AbortController();

    setStatus("loading");
    setStreamingText("");
    if (!isFollowUp) {
      setFinalText("");
      setErrorMsg(null);
      setFollowUp(null);
      setCollapsed(false);
    } else {
      setErrorMsg(null);
    }

    let collected = "";

    try {
      await streamCoworkChat({
        baseUrl,
        token: helperToken || undefined,
        mode: "start",
        conversationId: conversationId.current,
        prompt: resolvedPrompt,
        model: model || undefined,
        cwd: cwd || undefined,
        maxTurns: 6,
        signal: abortRef.current.signal,
        onEvent: (event: CoworkStreamEvent) => {
          if (event.type === "message") {
            setStatus("streaming");
            const delta = parseSseLineForDelta(event.line);
            if (delta) {
              collected += delta;
              setStreamingText(collected);
            }
          } else if (event.type === "done") {
            const text = collected.trim();
            setStreamingText("");

            if (mode === "briefing") {
              // Append AI response to chat history; stay "idle" so user can follow up
              if (text) {
                setChatHistory((prev) => [...prev, { role: "assistant", content: text }]);
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
            setStatus("error");
          }
        },
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setStatus("idle");
        return;
      }
      setErrorMsg(err instanceof Error ? err.message : "串流失敗");
      setStatus("error");
    }
  }, [mode, deal, activities, company, contacts, triggerActivity, onStreamComplete, aiEntries]);

  // Auto-start debrief on mount
  useEffect(() => {
    if (mode === "debrief" && triggerActivity) {
      startStream();
    }
    return () => {
      abortRef.current?.abort();
    };
  }, []); // Run once on mount

  // Auto-scroll to bottom when chat history updates
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, streamingText]);

  function handleCancel() {
    abortRef.current?.abort();
    setStatus("idle");
  }

  async function handleSendMessage() {
    if (!userInput.trim() || status !== "idle") return;

    const message = userInput.trim();
    setUserInput("");
    setChatHistory((prev) => [...prev, { role: "user", content: message }]);
    setTurnCount((t) => t + 1);

    const followUpPrompt = `/crm-briefing\n\n使用者追問（基於前面的會議準備對話）：\n${message}\n\n請根據之前的 briefing context 回答。`;
    await startStream(followUpPrompt, true);
  }

  const displayText = status === "streaming" ? streamingText : finalText;

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-secondary/20">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">{title}</span>
          {status === "loading" && (
            <span className="text-xs text-muted-foreground animate-pulse">初始化中...</span>
          )}
          {status === "streaming" && (
            <span className="text-xs text-primary animate-pulse">AI 回覆中</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {(status === "done" || status === "error" || (mode === "briefing" && chatHistory.length > 0)) && (
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="p-1 rounded hover:bg-secondary transition-colors"
              aria-label={collapsed ? "展開" : "收合"}
            >
              {collapsed ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronUp className="h-4 w-4 text-muted-foreground" />}
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground text-xs px-2"
            >
              關閉
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      {!collapsed && (
        <div>
          {/* ── Helper offline fallback (both modes) ── */}
          {helperOffline && status === "idle" && (
            <div className="m-4 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
              <PlugZap className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-sm text-amber-300">
                <p className="font-medium">Local Helper 未連線</p>
                <p className="text-xs text-amber-400 mt-0.5">請先啟動 Local Helper（port 4317），再重試。</p>
              </div>
              <button
                onClick={() => startStream()}
                className="ml-auto shrink-0 px-3 py-1 text-xs rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors"
              >
                重試
              </button>
            </div>
          )}

          {mode === "briefing" ? (
            /* ══ Briefing: conversational UI ══ */
            <div className="flex flex-col">
              {/* CTA button — only when no chat has started yet */}
              {status === "idle" && !helperOffline && chatHistory.length === 0 && (
                <div className="p-4">
                  <button
                    onClick={() => startStream()}
                    className="w-full py-3 text-sm font-medium rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 transition-colors flex items-center justify-center gap-2"
                  >
                    <Bot className="h-4 w-4" />
                    準備下次會議
                  </button>
                </div>
              )}

              {/* Chat history — scrollable */}
              {chatHistory.length > 0 && (
                <div className="overflow-y-auto max-h-[400px] space-y-4 p-4">
                  {chatHistory.map((msg, i) => (
                    <div key={i} className={msg.role === "user" ? "text-right" : ""}>
                      <span className="text-xs text-muted-foreground">
                        {msg.role === "user" ? "你" : "Claude"}
                      </span>
                      <div
                        className={`mt-1 p-3 rounded-lg text-sm ${
                          msg.role === "user"
                            ? "bg-blue-50 dark:bg-blue-950/40 ml-auto max-w-[80%] inline-block text-left"
                            : "bg-secondary/30"
                        }`}
                      >
                        {msg.role === "assistant" ? (
                          <MarkdownRenderer content={msg.content} className="text-sm text-foreground space-y-1" />
                        ) : (
                          <p className="text-sm text-foreground">{msg.content}</p>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Streaming — show latest AI response inline */}
                  {(status === "streaming" || status === "loading") && (
                    <div>
                      <span className="text-xs text-muted-foreground">Claude</span>
                      <div className="mt-1 p-3 rounded-lg text-sm bg-secondary/30">
                        {status === "loading" ? (
                          <div className="flex items-center gap-2 text-muted-foreground">
                            <RefreshCw className="h-3 w-3 animate-spin" />
                            <span>連線中...</span>
                          </div>
                        ) : (
                          <MarkdownRenderer content={streamingText} className="text-sm text-foreground space-y-1" />
                        )}
                      </div>
                    </div>
                  )}

                  <div ref={chatEndRef} />
                </div>
              )}

              {/* Loading spinner before first response */}
              {status === "loading" && chatHistory.length === 0 && (
                <div className="flex items-center justify-center py-8 gap-2 text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span className="text-sm">連線中...</span>
                </div>
              )}

              {/* Streaming first response (no history yet) */}
              {status === "streaming" && chatHistory.length === 0 && streamingText && (
                <div className="p-4">
                  <span className="text-xs text-muted-foreground">Claude</span>
                  <div className="mt-1 p-3 rounded-lg text-sm bg-secondary/30">
                    <MarkdownRenderer content={streamingText} className="text-sm text-foreground space-y-1" />
                  </div>
                </div>
              )}

              {/* Cancel button while streaming */}
              {status === "streaming" && (
                <div className="flex justify-end px-4 pb-2">
                  <button
                    onClick={handleCancel}
                    className="px-3 py-1 text-xs rounded-lg text-muted-foreground hover:text-foreground border border-border hover:border-foreground/30 transition-colors"
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
                    className="px-4 py-1.5 text-xs rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors flex items-center gap-1.5"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重試
                  </button>
                </div>
              )}

              {/* Input area — show after first response, while under turn limit */}
              {status !== "streaming" && status !== "loading" && chatHistory.length > 0 && turnCount < MAX_TURNS && (
                <div className="border-t border-border p-3 flex gap-2">
                  <input
                    type="text"
                    className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="追問或調整重點..."
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void handleSendMessage();
                      }
                    }}
                  />
                  <button
                    onClick={() => void handleSendMessage()}
                    disabled={!userInput.trim()}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    送出
                  </button>
                </div>
              )}

              {/* Turn limit reached */}
              {turnCount >= MAX_TURNS && (
                <div className="border-t border-border p-3 text-sm text-muted-foreground text-center">
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
                    className="w-full py-2 text-sm border border-border rounded-md hover:bg-secondary/50 transition-colors text-muted-foreground"
                  >
                    複製最新準備摘要
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* ══ Debrief: original single-shot UI ══ */
            <div className="p-4 space-y-4">
              {/* Loading spinner */}
              {status === "loading" && (
                <div className="flex items-center justify-center py-8 gap-2 text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span className="text-sm">連線中...</span>
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
                        className="px-3 py-1 text-xs rounded-lg text-muted-foreground hover:text-foreground border border-border hover:border-foreground/30 transition-colors"
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
                    className="px-4 py-1.5 text-xs rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors flex items-center gap-1.5"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重試
                  </button>
                </div>
              )}

              {/* Follow-up draft */}
              {status === "done" && followUp && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    Follow-up 草稿
                  </h4>
                  <FollowUpDraftUI draft={followUp} />
                </div>
              )}

              {/* Stage advance */}
              {status === "done" && onStageAdvanced && (
                <div className="pt-2 border-t border-border">
                  <p className="text-xs text-muted-foreground mb-2">如 AI 建議推進漏斗階段：</p>
                  <StageAdvanceButton deal={deal} token={token} onAdvanced={onStageAdvanced} />
                </div>
              )}

              {/* Re-run after done */}
              {status === "done" && (
                <div className="flex justify-end">
                  <button
                    onClick={() => startStream()}
                    className="px-3 py-1.5 text-xs rounded-lg text-muted-foreground hover:text-foreground border border-border hover:border-foreground/30 transition-colors flex items-center gap-1.5"
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
    </div>
  );
}
