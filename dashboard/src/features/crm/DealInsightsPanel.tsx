"use client";

/**
 * DealInsightsPanel — always-visible AI insights sidebar for the Deal detail page.
 *
 * Displays four collapsible sections derived from accumulated AI debrief entries:
 * - Key Decisions
 * - Commitment Tracking (ours vs customer, with completion checkbox)
 * - Customer Concerns
 * - Deal Summary (latest stage recommendation + next steps)
 */

import { useEffect, useState } from "react";
import {
  fetchDealAiEntries,
  deleteBriefing,
  updateCommitmentStatus,
} from "@/lib/crm-api";
import type { AiInsight, DealAiEntries } from "@/lib/crm-api";

// ─── Types ─────────────────────────────────────────────────────────────────────

interface DealInsightsPanelProps {
  dealId: string;
  token: string;
  /** Increment to trigger a re-fetch after debrief is saved */
  refreshKey: number;
  entries?: DealAiEntries | null;
  onOpenBriefing: (briefing: AiInsight) => void;
  onBriefingDeleted: (briefingId: string) => void;
}

interface DebriefMetadata {
  key_decisions?: string[];
  customer_concerns?: string[];
  next_steps?: string[];
  stage_recommendation?: string;
}

interface CommitmentMetadata {
  content?: string;
  owner?: "us" | "customer";
  deadline?: string;
}

interface BriefingMetadata {
  title?: string;
  chat_history?: Array<{ role?: string; content?: string }>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function isOverdue(deadline: string | undefined, status: string): boolean {
  if (!deadline || status !== "open") return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return new Date(deadline) < today;
}

// ─── SectionHeader ─────────────────────────────────────────────────────────────

interface SectionHeaderProps {
  title: string;
  open: boolean;
  onToggle: () => void;
  count?: number;
}

function SectionHeader({ title, open, onToggle, count }: SectionHeaderProps) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between py-2 text-left group"
    >
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-dim select-none">
          {open ? "▾" : "▸"}
        </span>
        <span className="text-sm font-medium text-foreground">{title}</span>
        {count !== undefined && count > 0 && (
          <span className="text-xs bg-soft text-dim rounded-full px-1.5">
            {count}
          </span>
        )}
      </div>
    </button>
  );
}

// ─── CommitmentItem ────────────────────────────────────────────────────────────

interface CommitmentItemProps {
  insight: AiInsight;
  token: string;
  onStatusChange: (updated: AiInsight) => void;
}

function CommitmentItem({ insight, token, onStatusChange }: CommitmentItemProps) {
  const meta = insight.metadata as CommitmentMetadata;
  const [updating, setUpdating] = useState(false);
  const done = insight.status === "done";
  const overdue = isOverdue(meta.deadline, insight.status);

  async function handleToggle() {
    setUpdating(true);
    try {
      const newStatus = done ? "open" : "done";
      const updated = await updateCommitmentStatus(token, insight.id, newStatus);
      onStatusChange(updated);
    } catch {
      // silent — UX stays consistent; user can retry
    }
    setUpdating(false);
  }

  return (
    <div
      className={`flex items-start gap-2 py-1.5 ${done ? "opacity-50" : ""}`}
    >
      <input
        type="checkbox"
        checked={done}
        disabled={updating}
        onChange={handleToggle}
        className="mt-0.5 h-3.5 w-3.5 rounded bd-hair accent-primary shrink-0 cursor-pointer"
      />
      <div className="min-w-0 flex-1">
        <p
          className={`text-xs leading-snug ${
            done
              ? "line-through text-dim"
              : overdue
              ? "text-red-400"
              : "text-foreground"
          }`}
        >
          {meta.content ?? insight.content}
        </p>
        {meta.deadline && (
          <p
            className={`text-[10px] mt-0.5 ${
              overdue ? "text-red-400 font-medium" : "text-dim"
            }`}
          >
            {overdue ? "逾期：" : "預期："}
            {meta.deadline}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── DealInsightsPanel ─────────────────────────────────────────────────────────

export function DealInsightsPanel({
  dealId,
  token,
  refreshKey,
  entries: externalEntries,
  onOpenBriefing,
  onBriefingDeleted,
}: DealInsightsPanelProps) {
  const [fetchedEntries, setFetchedEntries] = useState<DealAiEntries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingBriefingId, setDeletingBriefingId] = useState<string | null>(null);

  // Section open/collapsed state — all open by default
  const [openSections, setOpenSections] = useState({
    briefings: true,
    decisions: true,
    commitments: true,
    concerns: true,
    summary: true,
  });

  useEffect(() => {
    if (!token || !dealId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDealAiEntries(token, dealId)
      .then((data) => {
        if (!cancelled) setFetchedEntries(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "載入失敗");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token, dealId, refreshKey]);

  const entries = externalEntries ?? fetchedEntries;

  function toggleSection(key: keyof typeof openSections) {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function handleCommitmentChange(updated: AiInsight) {
    setFetchedEntries((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        commitments: prev.commitments.map((c) =>
          c.id === updated.id ? updated : c
        ),
      };
    });
  }

  async function handleDeleteBriefing(briefingId: string) {
    if (!window.confirm("要刪除這份 briefing 嗎？刪除後無法復原。")) {
      return;
    }

    setDeletingBriefingId(briefingId);
    try {
      await deleteBriefing(token, briefingId);
      setFetchedEntries((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          briefings: prev.briefings.filter((b) => b.id !== briefingId),
        };
      });
      onBriefingDeleted(briefingId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除 briefing 失敗");
    }
    setDeletingBriefingId(null);
  }

  // ── Derived data ─────────────────────────────────────────────────────────────

  const briefingsSorted = [...(entries?.briefings ?? [])].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );
  const debriefsSorted = [...(entries?.debriefs ?? [])].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  const allDecisions: Array<{ date: string; text: string }> = debriefsSorted.flatMap(
    (d) => {
      const meta = d.metadata as DebriefMetadata;
      return (meta.key_decisions ?? []).map((text) => ({
        date: formatDate(d.createdAt),
        text,
      }));
    }
  );

  const allConcerns: Array<{ date: string; text: string }> = debriefsSorted.flatMap(
    (d) => {
      const meta = d.metadata as DebriefMetadata;
      return (meta.customer_concerns ?? []).map((text) => ({
        date: formatDate(d.createdAt),
        text,
      }));
    }
  );

  const latestDebrief = debriefsSorted[0];
  const latestMeta = latestDebrief
    ? (latestDebrief.metadata as DebriefMetadata)
    : null;

  const openCommitments = entries?.commitments.filter((c) => c.status !== "done") ?? [];
  const doneCommitments = entries?.commitments.filter((c) => c.status === "done") ?? [];

  const ourCommitments = openCommitments.filter(
    (c) => (c.metadata as CommitmentMetadata).owner === "us"
  );
  const customerCommitments = openCommitments.filter(
    (c) => (c.metadata as CommitmentMetadata).owner === "customer"
  );

  const hasAnyData =
    entries !== null &&
    (
      briefingsSorted.length > 0 ||
      debriefsSorted.length > 0 ||
      (entries.commitments?.length ?? 0) > 0
    );

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="bg-panel border bd-hair rounded-zen p-4 space-y-1">
      <h3 className="text-sm font-semibold text-foreground mb-2">AI 洞察</h3>

      {loading && (
        <p className="text-xs text-dim py-4 text-center">
          載入洞察中...
        </p>
      )}

      {!loading && error && (
        <p className="text-xs text-red-400 py-2">{error}</p>
      )}

      {!loading && !error && !hasAnyData && (
        <p className="text-xs text-dim py-4 leading-relaxed">
          完成第一次商談並記錄活動後，AI 洞察將在這裡累積
        </p>
      )}

      {!loading && !error && hasAnyData && (
        <div className="divide-y divide-border">
          {/* ── Saved Briefings ── */}
          <div className="pb-2">
            <SectionHeader
              title="已存 Briefings"
              open={openSections.briefings}
              onToggle={() => toggleSection("briefings")}
              count={briefingsSorted.length}
            />
            {openSections.briefings && (
              <div className="space-y-2 mt-1">
                {briefingsSorted.length === 0 ? (
                  <p className="text-xs text-dim">尚無已存 briefing</p>
                ) : (
                  briefingsSorted.map((briefing) => {
                    const meta = briefing.metadata as BriefingMetadata;
                    const title = meta.title?.trim() || `會議準備 ${formatDate(briefing.createdAt)}`;
                    const lastAssistant =
                      [...(meta.chat_history ?? [])]
                        .reverse()
                        .find((item) => item.role === "assistant" && item.content?.trim())
                        ?.content ??
                      briefing.content;
                    return (
                      <div
                        key={briefing.id}
                        className="rounded-lg border bd-hair p-2 space-y-1"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-foreground truncate">
                              {title}
                            </p>
                            <p className="text-[10px] text-dim">
                              {formatDate(briefing.createdAt)}
                            </p>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => onOpenBriefing(briefing)}
                              className="px-2 py-1 text-[10px] rounded border bd-hair text-dim hover:text-foreground hover:border-foreground/30 transition-colors"
                            >
                              開啟
                            </button>
                            <button
                              onClick={() => void handleDeleteBriefing(briefing.id)}
                              disabled={deletingBriefingId === briefing.id}
                              className="px-2 py-1 text-[10px] rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                            >
                              刪除
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-dim line-clamp-3 whitespace-pre-wrap">
                          {lastAssistant?.trim() || "—"}
                        </p>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>

          {/* ── 關鍵決策 ── */}
          <div className="pb-2">
            <SectionHeader
              title="關鍵決策"
              open={openSections.decisions}
              onToggle={() => toggleSection("decisions")}
              count={allDecisions.length}
            />
            {openSections.decisions && (
              <div className="space-y-1.5 mt-1">
                {allDecisions.length === 0 ? (
                  <p className="text-xs text-dim">尚無決策記錄</p>
                ) : (
                  allDecisions.map((item, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="text-[10px] text-dim shrink-0 mt-0.5">
                        {item.date}
                      </span>
                      <p className="text-xs text-foreground">{item.text}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* ── 承諾追蹤 ── */}
          <div className="py-2">
            <SectionHeader
              title="承諾追蹤"
              open={openSections.commitments}
              onToggle={() => toggleSection("commitments")}
              count={openCommitments.length}
            />
            {openSections.commitments && (
              <div className="mt-1 space-y-2">
                {ourCommitments.length === 0 && customerCommitments.length === 0 && doneCommitments.length === 0 ? (
                  <p className="text-xs text-dim">尚無承諾追蹤</p>
                ) : (
                  <>
                    {ourCommitments.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium text-dim uppercase tracking-wide mb-1">
                          我方承諾
                        </p>
                        {ourCommitments.map((c) => (
                          <CommitmentItem
                            key={c.id}
                            insight={c}
                            token={token}
                            onStatusChange={handleCommitmentChange}
                          />
                        ))}
                      </div>
                    )}
                    {customerCommitments.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium text-dim uppercase tracking-wide mb-1">
                          客戶承諾
                        </p>
                        {customerCommitments.map((c) => (
                          <CommitmentItem
                            key={c.id}
                            insight={c}
                            token={token}
                            onStatusChange={handleCommitmentChange}
                          />
                        ))}
                      </div>
                    )}
                    {doneCommitments.length > 0 && (
                      <details className="mt-3">
                        <summary className="text-sm text-dim cursor-pointer hover:text-foreground">
                          已完成（{doneCommitments.length}）
                        </summary>
                        <div className="mt-2 space-y-2">
                          {doneCommitments.map((c) => (
                            <CommitmentItem
                              key={c.id}
                              insight={c}
                              token={token}
                              onStatusChange={handleCommitmentChange}
                            />
                          ))}
                        </div>
                      </details>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* ── 客戶顧慮 ── */}
          <div className="py-2">
            <SectionHeader
              title="客戶顧慮"
              open={openSections.concerns}
              onToggle={() => toggleSection("concerns")}
              count={allConcerns.length}
            />
            {openSections.concerns && (
              <div className="space-y-1.5 mt-1">
                {allConcerns.length === 0 ? (
                  <p className="text-xs text-dim">尚無客戶顧慮記錄</p>
                ) : (
                  allConcerns.map((item, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="text-[10px] text-dim shrink-0 mt-0.5">
                        {item.date}
                      </span>
                      <p className="text-xs text-foreground">{item.text}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* ── Deal 摘要 ── */}
          <div className="pt-2">
            <SectionHeader
              title="Deal 摘要"
              open={openSections.summary}
              onToggle={() => toggleSection("summary")}
            />
            {openSections.summary && (
              <div className="space-y-2 mt-1">
                {!latestMeta ? (
                  <p className="text-xs text-dim">尚無摘要</p>
                ) : (
                  <>
                    {latestMeta.stage_recommendation && (
                      <div>
                        <p className="text-[10px] font-medium text-dim uppercase tracking-wide mb-0.5">
                          階段建議
                        </p>
                        <p className="text-xs text-foreground">
                          {latestMeta.stage_recommendation}
                        </p>
                      </div>
                    )}
                    {latestMeta.next_steps && latestMeta.next_steps.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium text-dim uppercase tracking-wide mb-0.5">
                          下一步
                        </p>
                        <ul className="space-y-0.5">
                          {latestMeta.next_steps.map((step, i) => (
                            <li key={i} className="text-xs text-foreground flex gap-1">
                              <span className="text-dim shrink-0">·</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {!latestMeta.stage_recommendation &&
                      (!latestMeta.next_steps ||
                        latestMeta.next_steps.length === 0) && (
                        <p className="text-xs text-dim">
                          最近 debrief 尚無摘要資料
                        </p>
                      )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
