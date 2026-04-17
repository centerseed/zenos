"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LoadingState } from "@/components/LoadingState";
import {
  getDeal,
  getCompany,
  getCompanyContacts,
  patchDealStage,
  getDealActivities,
  createActivity,
  createAiInsight,
  fetchDealAiEntries,
} from "@/lib/crm-api";
import type {
  Deal,
  Activity,
  FunnelStage,
  ActivityType,
  Company,
  Contact,
  AiInsight,
  DealAiEntries,
} from "@/lib/crm-api";
import { CrmAiPanel } from "@/features/crm/CrmAiPanel";
import { DealInsightsPanel } from "@/features/crm/DealInsightsPanel";

// ─── Constants ────────────────────────────────────────────────────────────────

const FUNNEL_STAGES: FunnelStage[] = [
  "潛在客戶",
  "需求訪談",
  "提案報價",
  "合約議價",
  "導入中",
  "結案",
];

const ACTIVITY_TYPES: ActivityType[] = ["電話", "Email", "會議", "Demo", "備忘"];

/** Activity types that trigger an automatic debrief after creation */
const DEBRIEF_TRIGGER_TYPES = new Set<ActivityType>(["會議", "Demo", "電話"]);

// ─── Debrief metadata parsing ─────────────────────────────────────────────────

function extractDebriefMetadata(text: string): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};

  const decisionsMatch = text.match(/##\s*關鍵決策\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (decisionsMatch) {
    metadata.key_decisions = decisionsMatch[1]
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => l.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const concernsMatch = text.match(/##\s*客戶顧慮\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (concernsMatch) {
    metadata.customer_concerns = concernsMatch[1]
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => l.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const nextStepsMatch = text.match(/##\s*下一步行動\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (nextStepsMatch) {
    metadata.next_steps = nextStepsMatch[1]
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => l.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const stageMatch = text.match(/##\s*階段建議\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (stageMatch) {
    metadata.stage_recommendation = stageMatch[1].trim();
  }

  // Reuse follow-up extraction pattern for LINE / Email metadata
  const lineMatch = text.match(/##\s*(?:LINE|Line|line)[^\n]*\n([\s\S]*?)(?=##|$)/);
  const emailMatch = text.match(/##\s*(?:Email|email|電子郵件|郵件)[^\n]*\n([\s\S]*?)(?=##|$)/);

  if (lineMatch || emailMatch) {
    const followUp: Record<string, unknown> = {
      line: lineMatch ? lineMatch[1].trim() : "",
    };
    if (emailMatch) {
      const emailContent = emailMatch[1].trim();
      const subjectMatch = emailContent.match(/(?:\*\*主旨[:：]\*\*|主旨[:：])\s*(.+)/);
      if (subjectMatch) {
        followUp.email = {
          subject: subjectMatch[1].trim(),
          body: emailContent.replace(subjectMatch[0], "").trim(),
        };
      } else {
        const lines = emailContent.split("\n");
        followUp.email = {
          subject: lines[0].replace(/^[*#\-\s]+/, "").trim(),
          body: lines.slice(1).join("\n").trim(),
        };
      }
    }
    metadata.follow_up = followUp;
  }

  return metadata;
}

interface CommitmentRaw {
  content: string;
  owner: "us" | "customer";
  deadline?: string;
}

function extractCommitments(text: string): CommitmentRaw[] {
  const commitments: CommitmentRaw[] = [];

  const sectionMatch = text.match(/##\s*承諾事項\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (!sectionMatch) return commitments;

  const section = sectionMatch[1];

  // Split into our-side and customer-side subsections
  const ourMatch = section.match(/我方承諾[：:]\s*\n([\s\S]*?)(?=客戶承諾|$)/);
  const customerMatch = section.match(/客戶承諾[：:]\s*\n([\s\S]*?)(?=$)/);

  function parseItems(
    block: string,
    owner: "us" | "customer"
  ): CommitmentRaw[] {
    return block
      .split("\n")
      .filter((l) => l.trim().startsWith("-"))
      .map((l) => {
        const raw = l.replace(/^-\s*/, "").trim();
        // Format: [事項] — 預期時間：[日期]
        const deadlineMatch = raw.match(/[—–-]\s*預期時間[：:]\s*(.+)$/);
        const content = deadlineMatch
          ? raw.replace(deadlineMatch[0], "").trim()
          : raw;
        return {
          content,
          owner,
          ...(deadlineMatch ? { deadline: deadlineMatch[1].trim() } : {}),
        };
      })
      .filter((c) => c.content.length > 0);
  }

  if (ourMatch) commitments.push(...parseItems(ourMatch[1], "us"));
  if (customerMatch) commitments.push(...parseItems(customerMatch[1], "customer"));

  return commitments;
}

// ─── ActivityItem ─────────────────────────────────────────────────────────────

interface ActivityItemProps {
  activity: Activity;
  matchingDebrief?: AiInsight;
}

function ActivityItem({ activity, matchingDebrief }: ActivityItemProps) {
  const date = activity.activityAt;
  const dateStr =
    date instanceof Date
      ? date.toLocaleDateString("zh-TW", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        })
      : String(date);

  const debriefMeta = matchingDebrief?.metadata as
    | { key_decisions?: string[]; next_steps?: string[] }
    | undefined;

  return (
    <div className={`flex gap-3 ${activity.isSystem ? "opacity-60" : ""}`}>
      <div className="flex flex-col items-center">
        <div
          className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
            activity.isSystem ? "bg-muted-foreground" : "bg-primary"
          }`}
        />
        <div className="w-px flex-1 bg-border mt-1" />
      </div>
      <div className="pb-4 min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span
            className={`text-xs rounded px-1.5 py-0.5 ${
              activity.isSystem
                ? "bg-secondary text-muted-foreground"
                : "bg-primary/15 text-primary"
            }`}
          >
            {activity.activityType}
          </span>
          <span className="text-xs text-muted-foreground">{dateStr}</span>
        </div>
        <p className="text-sm text-foreground">{activity.summary}</p>

        {/* Inline AI analysis — only for non-system activities that have a debrief */}
        {!activity.isSystem && matchingDebrief && debriefMeta && (
          <details className="mt-2 ml-0 text-sm">
            <summary className="cursor-pointer text-blue-600 hover:text-blue-800 text-xs select-none">
              AI 分析 ▸
            </summary>
            <div className="mt-1 pl-3 border-l-2 border-blue-200 text-muted-foreground space-y-1">
              {debriefMeta.key_decisions && debriefMeta.key_decisions.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-foreground">關鍵決策：</span>
                  <ul className="list-disc ml-4 mt-0.5">
                    {debriefMeta.key_decisions.map((d, i) => (
                      <li key={i} className="text-xs">
                        {d}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {debriefMeta.next_steps && debriefMeta.next_steps.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-foreground">下一步：</span>
                  <ul className="list-disc ml-4 mt-0.5">
                    {debriefMeta.next_steps.map((s, i) => (
                      <li key={i} className="text-xs">
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

// ─── New Activity Form ────────────────────────────────────────────────────────

interface NewActivityFormProps {
  dealId: string;
  token: string;
  recordedBy: string;
  onCreated: (activity: Activity) => void;
}

function NewActivityForm({
  dealId,
  token,
  recordedBy,
  onCreated,
}: NewActivityFormProps) {
  const [activityType, setActivityType] = useState<ActivityType>("會議");
  const [summary, setSummary] = useState("");
  const [activityAt, setActivityAt] = useState(
    new Date().toISOString().slice(0, 16)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const activity = await createActivity(token, dealId, {
        activityType,
        activityAt: new Date(activityAt),
        summary: summary.trim(),
        recordedBy,
      });
      onCreated(activity);
      setSummary("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立失敗");
    }
    setSaving(false);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-secondary/20 border border-border rounded-xl p-4 space-y-3"
    >
      <h4 className="text-sm font-medium text-foreground">新增活動</h4>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">類型</label>
          <select
            value={activityType}
            onChange={(e) => setActivityType(e.target.value as ActivityType)}
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {ACTIVITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">
            日期時間
          </label>
          <input
            type="datetime-local"
            value={activityAt}
            onChange={(e) => setActivityAt(e.target.value)}
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">
          摘要 <span className="text-red-400">*</span>
        </label>
        <textarea
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="本次互動的重點..."
          rows={3}
          required
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving || !summary.trim()}
          className="px-4 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? "建立中..." : "新增活動"}
        </button>
      </div>
    </form>
  );
}

// ─── DealDetailPage ───────────────────────────────────────────────────────────

function DealDetailPage() {
  const { user, partner } = useAuth();
  const params = useParams();
  const [dealId, setDealId] = useState<string>("");

  useEffect(() => {
    const rawParam = params.id;
    const paramId = Array.isArray(rawParam) ? rawParam[0] : rawParam;
    if (paramId && paramId !== "_") {
      setDealId(paramId);
      return;
    }

    if (typeof window !== "undefined") {
      const segments = window.location.pathname.split("/").filter(Boolean);
      const fallbackId = segments[segments.length - 1];
      if (fallbackId && fallbackId !== "_") {
        setDealId(fallbackId);
      }
    }
  }, [params]);

  const [deal, setDeal] = useState<Deal | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState("");
  const [stageUpdating, setStageUpdating] = useState(false);

  // AI panel state
  const [showBriefing, setShowBriefing] = useState(false);
  const [selectedBriefing, setSelectedBriefing] = useState<AiInsight | null>(null);
  const [debriefActivity, setDebriefActivity] = useState<Activity | null>(null);

  // AI insights panel state
  const [aiEntries, setAiEntries] = useState<DealAiEntries | null>(null);
  const [insightsRefreshKey, setInsightsRefreshKey] = useState(0);

  useEffect(() => {
    if (!user || !partner || !dealId) return;

    async function load() {
      const t = await user!.getIdToken();
      setToken(t);
      try {
        const [fetchedDeal, fetchedActivities] = await Promise.all([
          getDeal(t, dealId),
          getDealActivities(t, dealId),
        ]);
        setDeal(fetchedDeal);
        setActivities(
          [...fetchedActivities].sort(
            (a, b) => b.activityAt.getTime() - a.activityAt.getTime()
          )
        );
        const [fetchedCompany, fetchedContacts, fetchedAiEntries] = await Promise.all([
          getCompany(t, fetchedDeal.companyId),
          getCompanyContacts(t, fetchedDeal.companyId),
          fetchDealAiEntries(t, dealId),
        ]);
        setCompany(fetchedCompany);
        setContacts(fetchedContacts);
        setAiEntries(fetchedAiEntries);
      } catch (err) {
        console.error("Failed to load deal:", err);
      }
      setLoading(false);
    }

    load();
  }, [user, partner, dealId]);

  async function handleStageChange(newStage: FunnelStage) {
    if (!deal || deal.funnelStage === newStage) return;
    setStageUpdating(true);
    try {
      const updated = await patchDealStage(token, dealId, newStage);
      setDeal(updated);
    } catch (err) {
      console.error("Failed to update stage:", err);
    }
    setStageUpdating(false);
  }

  function handleActivityCreated(activity: Activity) {
    setActivities((prev) =>
      [activity, ...prev].sort(
        (a, b) => b.activityAt.getTime() - a.activityAt.getTime()
      )
    );
    if (DEBRIEF_TRIGGER_TYPES.has(activity.activityType)) {
      setDebriefActivity(activity);
      setShowBriefing(false);
    }
  }

  /**
   * Called when debrief streaming completes.
   * Parses AI output, saves debrief + commitments via API, then refreshes the
   * insights panel.
   */
  async function handleDebriefStreamComplete(finalText: string) {
    if (!finalText.trim() || !debriefActivity) return;

    const metadata = extractDebriefMetadata(finalText);
    const commitments = extractCommitments(finalText);

    try {
      // Save debrief
      const saved = await createAiInsight(token, dealId, {
        insightType: "debrief",
        content: finalText,
        metadata,
        activityId: debriefActivity.id,
      });

      // Update local aiEntries so inline debrief in timeline shows immediately
      setAiEntries((prev) => ({
        briefings: prev?.briefings ?? [],
        debriefs: [saved, ...(prev?.debriefs ?? [])],
        commitments: prev?.commitments ?? [],
      }));

      // Save each commitment
      const savedCommitments: AiInsight[] = [];
      for (const c of commitments) {
        try {
          const savedCommitment = await createAiInsight(token, dealId, {
            insightType: "commitment",
            content: c.content,
            metadata: {
              content: c.content,
              owner: c.owner,
              ...(c.deadline ? { deadline: c.deadline } : {}),
            },
            activityId: debriefActivity.id,
          });
          savedCommitments.push(savedCommitment);
        } catch (err) {
          console.error("Failed to save commitment:", err);
        }
      }

      if (savedCommitments.length > 0) {
        setAiEntries((prev) => ({
          briefings: prev?.briefings ?? [],
          debriefs: prev?.debriefs ?? [],
          commitments: [...savedCommitments, ...(prev?.commitments ?? [])],
        }));
      }

      // Trigger DealInsightsPanel re-fetch
      setInsightsRefreshKey((k) => k + 1);
    } catch (err) {
      console.error("Failed to save debrief:", err);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen">
        <div className="flex-1 flex items-center justify-center py-20">
          <LoadingState label="載入商機資料..." />
        </div>
      </div>
    );
  }

  if (!deal) {
    return (
      <div className="min-h-screen">
        <main className="max-w-3xl mx-auto px-4 py-6">
          <p className="text-muted-foreground">找不到該商機</p>
        </main>
      </div>
    );
  }

  const formatDate = (date: Date | undefined) =>
    date instanceof Date
      ? date.toLocaleDateString("zh-TW", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        })
      : "—";

  // Build a map from activityId → debrief for quick lookup in ActivityItem
  const debriefByActivityId = new Map<string, AiInsight>();
  for (const d of aiEntries?.debriefs ?? []) {
    if (d.activityId) debriefByActivityId.set(d.activityId, d);
  }

  function handleBriefingSaved(saved: AiInsight, mode: "create" | "update") {
    setAiEntries((prev) => {
      const current = prev ?? { briefings: [], debriefs: [], commitments: [] };
      return {
        ...current,
        briefings:
          mode === "create"
            ? [saved, ...current.briefings.filter((b) => b.id !== saved.id)]
            : current.briefings.map((b) => (b.id === saved.id ? saved : b)),
      };
    });
    setSelectedBriefing((prev) =>
      !prev || prev.id !== saved.id ? saved : prev
    );
    setInsightsRefreshKey((k) => k + 1);
  }

  function handleBriefingDeleted(briefingId: string) {
    setAiEntries((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        briefings: prev.briefings.filter((b) => b.id !== briefingId),
      };
    });
    if (selectedBriefing?.id === briefingId) {
      setSelectedBriefing(null);
      setShowBriefing(false);
    }
    setInsightsRefreshKey((k) => k + 1);
  }

  function handleOpenBriefing(briefing: AiInsight) {
    setSelectedBriefing(briefing);
    setDebriefActivity(null);
    setShowBriefing(true);
  }

  return (
    <div className="min-h-screen">
      <main
        id="main-content"
        className="max-w-screen-xl mx-auto px-4 sm:px-6 py-6 space-y-6"
      >
        {/* Breadcrumb — full width */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link
            href="/clients"
            className="hover:text-foreground transition-colors"
          >
            客戶
          </Link>
          <span>/</span>
          <span className="text-foreground">{deal.title}</span>
        </div>

        {/* Deal header — full width */}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="flex items-start justify-between gap-3 mb-4">
            <h2 className="text-xl font-semibold text-foreground">
              {deal.title}
            </h2>
            <div className="flex gap-1.5 shrink-0 flex-wrap justify-end items-center">
              {deal.isClosedLost && (
                <span className="text-xs bg-red-500/15 text-red-400 border border-red-500/30 rounded px-2 py-0.5">
                  流失
                </span>
              )}
              {deal.isOnHold && (
                <span className="text-xs bg-yellow-500/15 text-yellow-400 border border-yellow-500/30 rounded px-2 py-0.5">
                  暫緩
                </span>
              )}
              {!showBriefing && (
                <button
                  onClick={() => {
                    setShowBriefing(true);
                    setDebriefActivity(null);
                    setSelectedBriefing(null);
                  }}
                  className="px-3 py-1 text-xs rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  準備下次會議
                </button>
              )}
            </div>
          </div>

          {/* Funnel stage selector */}
          <div className="mb-4">
            <label className="block text-xs text-muted-foreground mb-1.5">
              漏斗階段
            </label>
            <div className="flex gap-1.5 flex-wrap">
              {FUNNEL_STAGES.map((stage) => (
                <button
                  key={stage}
                  onClick={() => handleStageChange(stage)}
                  disabled={stageUpdating}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    deal.funnelStage === stage
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
                  } disabled:opacity-50`}
                >
                  {stage}
                </button>
              ))}
            </div>
          </div>

          {/* Deal fields */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">案值</dt>
              <dd className="text-foreground">
                {deal.amountTwd
                  ? `NT$ ${deal.amountTwd.toLocaleString()}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">案子類型</dt>
              <dd className="text-foreground">{deal.dealType ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">來源</dt>
              <dd className="text-foreground">{deal.sourceType ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">介紹人</dt>
              <dd className="text-foreground">{deal.referrer ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">預計成交日</dt>
              <dd className="text-foreground">
                {formatDate(deal.expectedCloseDate)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">合約簽署日</dt>
              <dd className="text-foreground">{formatDate(deal.signedDate)}</dd>
            </div>
          </dl>

          {deal.scopeDescription && (
            <div className="mt-3 pt-3 border-t border-border">
              <dt className="text-xs text-muted-foreground mb-1">工作範圍</dt>
              <dd className="text-sm text-foreground">
                {deal.scopeDescription}
              </dd>
            </div>
          )}

          {deal.deliverables && deal.deliverables.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-xs text-muted-foreground mb-1">交付物</p>
              <ul className="list-disc list-inside space-y-0.5">
                {deal.deliverables.map((item, i) => (
                  <li key={i} className="text-sm text-foreground">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {deal.notes && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-xs text-muted-foreground mb-1">備忘</p>
              <p className="text-sm text-foreground">{deal.notes}</p>
            </div>
          )}
        </div>

        {/* Main content area — dual-column */}
        <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
          {/* Left column: AI Insights Panel — always visible */}
          <div className="order-2 lg:order-1">
            <DealInsightsPanel
              dealId={dealId}
              token={token}
              refreshKey={insightsRefreshKey}
              entries={aiEntries}
              onOpenBriefing={handleOpenBriefing}
              onBriefingDeleted={handleBriefingDeleted}
            />
          </div>

          {/* Right column: AI panels + activity form + timeline */}
          <div className="order-1 lg:order-2 space-y-6">
            {/* AI Briefing panel */}
            {showBriefing && (
              <CrmAiPanel
                mode="briefing"
                deal={deal}
                activities={activities}
                company={company}
                contacts={contacts}
                token={token}
                aiEntries={aiEntries}
                initialBriefing={selectedBriefing}
                onBriefingSaved={handleBriefingSaved}
                onClose={() => setShowBriefing(false)}
              />
            )}

            {/* AI Debrief panel — auto-shown after meeting/Demo/電話 activity */}
            {debriefActivity && (
              <CrmAiPanel
                key={debriefActivity.id}
                mode="debrief"
                deal={deal}
                activities={activities}
                company={company}
                contacts={contacts}
                token={token}
                triggerActivity={debriefActivity}
                onStageAdvanced={(updated: Deal) => {
                  setDeal(updated);
                  setDebriefActivity(null);
                }}
                onClose={() => setDebriefActivity(null)}
                onStreamComplete={handleDebriefStreamComplete}
              />
            )}

            {/* New activity form */}
            {partner && (
              <NewActivityForm
                dealId={dealId}
                token={token}
                recordedBy={partner.id}
                onCreated={handleActivityCreated}
              />
            )}

            {/* Activity timeline */}
            <section>
              <h3 className="text-sm font-semibold text-foreground mb-4">
                活動紀錄 ({activities.length})
              </h3>
              {activities.length === 0 ? (
                <p className="text-sm text-muted-foreground">尚無活動紀錄</p>
              ) : (
                <div>
                  {activities.map((activity) => (
                    <ActivityItem
                      key={activity.id}
                      activity={activity}
                      matchingDebrief={
                        debriefByActivityId.get(activity.id) ?? undefined
                      }
                    />
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function DealDetailClient() {
  return <DealDetailPage />;
}
