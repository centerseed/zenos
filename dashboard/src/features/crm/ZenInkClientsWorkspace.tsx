"use client";

/**
 * ZenInkClientsWorkspace — Zen Ink visual + real crm-api data.
 *
 * S03 of SPEC-zen-ink-real-data:
 * - Fetches deals + companies via getDeals / getCompanies
 * - Deal detail uses getDeal + getDealActivities + fetchDealAiEntries
 * - patchDealStage for stage advance
 * - Route guard: shared-workspace → /tasks  (same as ClientsWorkspace)
 * - Missing fields → "—"
 */

import React, { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { resolveActiveWorkspace } from "@/lib/partner";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Section } from "@/components/zen/Section";
import { Btn } from "@/components/zen/Btn";
import { Chip } from "@/components/zen/Chip";
import {
  getDeals,
  getCompanies,
  getDeal,
  getCompany,
  getCompanyContacts,
  getDealActivities,
  createActivity,
  createAiInsight,
  fetchDealAiEntries,
  patchDealStage,
} from "@/lib/crm-api";
import type {
  Deal,
  Company,
  Activity,
  DealAiEntries,
  FunnelStage,
  Contact,
  ActivityType,
  AiInsight,
} from "@/lib/crm-api";
import { CrmAiPanel } from "@/features/crm/CrmAiPanel";
import { NewDealModal } from "@/features/crm/ClientsWorkspace";

// ─── Stage definitions ────────────────────────────────────────────────────────

const FUNNEL_STAGES: FunnelStage[] = [
  "潛在客戶",
  "需求訪談",
  "提案報價",
  "合約議價",
  "導入中",
];

// "結案" is treated as won/closed for KPI; pipeline shows 5 active stages
const WON_STAGE: FunnelStage = "結案";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtAmount(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n) || n === 0) return "—";
  if (n >= 1000) return "$" + Math.round(n / 1000) + "k";
  return "$" + n;
}

function fmtDate(d: Date | undefined | null): string {
  if (!d) return "—";
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${m}/${day}`;
}

function stageIndex(stage: FunnelStage): number {
  const all: FunnelStage[] = [...FUNNEL_STAGES, WON_STAGE];
  return all.indexOf(stage);
}

function nextStage(current: FunnelStage): FunnelStage | null {
  const all: FunnelStage[] = [...FUNNEL_STAGES, WON_STAGE];
  const idx = all.indexOf(current);
  if (idx === -1 || idx >= all.length - 1) return null;
  return all[idx + 1];
}

function isThisMonth(d: Date): boolean {
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
}

const DEBRIEF_TRIGGER_TYPES = new Set<ActivityType>(["會議", "Demo", "電話"]);

interface CommitmentRaw {
  content: string;
  owner: "us" | "customer";
  deadline?: string;
}

function extractDebriefMetadata(text: string): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};

  const decisionsMatch = text.match(/##\s*關鍵決策\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (decisionsMatch) {
    metadata.key_decisions = decisionsMatch[1]
      .split("\n")
      .filter((line) => line.trim().startsWith("-"))
      .map((line) => line.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const concernsMatch = text.match(/##\s*客戶顧慮\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (concernsMatch) {
    metadata.customer_concerns = concernsMatch[1]
      .split("\n")
      .filter((line) => line.trim().startsWith("-"))
      .map((line) => line.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const nextStepsMatch = text.match(/##\s*下一步行動\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (nextStepsMatch) {
    metadata.next_steps = nextStepsMatch[1]
      .split("\n")
      .filter((line) => line.trim().startsWith("-"))
      .map((line) => line.replace(/^-\s*/, "").trim())
      .filter(Boolean);
  }

  const stageMatch = text.match(/##\s*階段建議\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (stageMatch) {
    metadata.stage_recommendation = stageMatch[1].trim();
  }

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

function extractCommitments(text: string): CommitmentRaw[] {
  const commitments: CommitmentRaw[] = [];
  const sectionMatch = text.match(/##\s*承諾事項\s*\n([\s\S]*?)(?=\n##|\n$|$)/);
  if (!sectionMatch) return commitments;

  const section = sectionMatch[1];
  const ourMatch = section.match(/我方承諾[：:]\s*\n([\s\S]*?)(?=客戶承諾|$)/);
  const customerMatch = section.match(/客戶承諾[：:]\s*\n([\s\S]*?)(?=$)/);

  function parseItems(block: string, owner: "us" | "customer"): CommitmentRaw[] {
    return block
      .split("\n")
      .filter((line) => line.trim().startsWith("-"))
      .map((line) => {
        const raw = line.replace(/^-\s*/, "").trim();
        const deadlineMatch = raw.match(/[—–-]\s*預期時間[：:]\s*(.+)$/);
        return {
          content: deadlineMatch ? raw.replace(deadlineMatch[0], "").trim() : raw,
          owner,
          ...(deadlineMatch ? { deadline: deadlineMatch[1].trim() } : {}),
        };
      })
      .filter((item) => item.content.length > 0);
  }

  if (ourMatch) commitments.push(...parseItems(ourMatch[1], "us"));
  if (customerMatch) commitments.push(...parseItems(customerMatch[1], "customer"));
  return commitments;
}

// ─── Loading state ────────────────────────────────────────────────────────────

function InkSpinner({ message }: { message: string }) {
  const t = useInk("light");
  const { c, fontMono } = t;
  return (
    <div
      style={{
        padding: "40px 48px 48px",
        maxWidth: 1600,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        gap: 16,
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          border: `2px solid ${c.inkHair}`,
          borderTopColor: c.vermillion,
          animation: "spin 0.8s linear infinite",
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <span
        style={{
          fontFamily: fontMono,
          fontSize: 12,
          color: c.inkMuted,
          letterSpacing: "0.1em",
        }}
      >
        {message}
      </span>
    </div>
  );
}

// ─── Error state ──────────────────────────────────────────────────────────────

function InkErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;
  return (
    <div style={{ padding: "40px 48px 48px", maxWidth: 1600 }}>
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.vermLine}`,
          borderRadius: 2,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          maxWidth: 480,
        }}
      >
        <span
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.vermillion,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          載入失敗
        </span>
        <p style={{ fontSize: 13, color: c.ink, margin: 0, lineHeight: 1.6 }}>
          {message}
        </p>
        <Btn t={t} variant="outline" onClick={onRetry}>
          重試
        </Btn>
      </div>
    </div>
  );
}

// ─── Deal detail ──────────────────────────────────────────────────────────────

interface DealDetailProps {
  dealId: string;
  companiesMap: Record<string, string>;
  onBack: () => void;
  userToken: () => Promise<string>;
  recordedBy: string | null;
}

function InkDealDetail({
  dealId,
  companiesMap,
  onBack,
  userToken,
  recordedBy,
}: DealDetailProps) {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;
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
  const [tab, setTab] = useState<"overview" | "activity" | "commits" | "files">(
    "overview"
  );

  const [deal, setDeal] = useState<Deal | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [aiEntries, setAiEntries] = useState<DealAiEntries | null>(null);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [showBriefing, setShowBriefing] = useState(false);
  const [selectedBriefing, setSelectedBriefing] = useState<AiInsight | null>(null);
  const [debriefActivity, setDebriefActivity] = useState<Activity | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await userToken();
      setToken(token);
      const fetchedDeal = await getDeal(token, dealId);
      const [fetchedActivities, fetchedAi, fetchedCompany, fetchedContacts] = await Promise.all([
        getDealActivities(token, dealId),
        fetchDealAiEntries(token, dealId),
        getCompany(token, fetchedDeal.companyId),
        getCompanyContacts(token, fetchedDeal.companyId),
      ]);
      setDeal(fetchedDeal);
      setActivities(fetchedActivities);
      setAiEntries(fetchedAi);
      setCompany(fetchedCompany);
      setContacts(fetchedContacts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入 Deal 資料");
    } finally {
      setLoading(false);
    }
  }, [dealId, userToken]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <InkSpinner message="載入商機詳情..." />;
  if (error) return <InkErrorCard message={error} onRetry={load} />;
  if (!deal) return null;

  const companyName = companiesMap[deal.companyId] ?? "—";
  const curStageIdx = stageIndex(deal.funnelStage);
  const allStages: FunnelStage[] = [...FUNNEL_STAGES, WON_STAGE];

  // AI briefing — use most recent briefing entry
  const latestBriefing =
    aiEntries && aiEntries.briefings.length > 0
      ? aiEntries.briefings[aiEntries.briefings.length - 1]
      : null;

  // Commitments from AI entries
  const commitments = aiEntries?.commitments ?? [];

  async function handleAdvanceStage() {
    if (!deal) return;
    const next = nextStage(deal.funnelStage);
    if (!next) return;
    setAdvancing(true);
    // optimistic update
    const prev = deal.funnelStage;
    setDeal((d) => (d ? { ...d, funnelStage: next } : d));
    try {
      const token = await userToken();
      const updated = await patchDealStage(token, deal.id, next);
      setDeal(updated);
    } catch {
      // rollback
      setDeal((d) => (d ? { ...d, funnelStage: prev } : d));
    } finally {
      setAdvancing(false);
    }
  }

  const canAdvance = nextStage(deal.funnelStage) !== null && !advancing;

  function handleActivityCreated(activity: Activity) {
    setActivities((prev) => [activity, ...prev]);
    if (DEBRIEF_TRIGGER_TYPES.has(activity.activityType)) {
      setDebriefActivity(activity);
      setShowBriefing(false);
    }
  }

  async function handleDebriefStreamComplete(finalText: string) {
    if (!finalText.trim() || !debriefActivity) return;
    const token = await userToken();
    const metadata = extractDebriefMetadata(finalText);
    const commitments = extractCommitments(finalText);

    const saved = await createAiInsight(token, dealId, {
      insightType: "debrief",
      content: finalText,
      metadata,
      activityId: debriefActivity.id,
    });

    setAiEntries((prev) => ({
      briefings: prev?.briefings ?? [],
      debriefs: [saved, ...(prev?.debriefs ?? [])],
      commitments: prev?.commitments ?? [],
    }));

    const savedCommitments: AiInsight[] = [];
    for (const commitment of commitments) {
      try {
        const savedCommitment = await createAiInsight(token, dealId, {
          insightType: "commitment",
          content: commitment.content,
          metadata: {
            content: commitment.content,
            owner: commitment.owner,
            ...(commitment.deadline ? { deadline: commitment.deadline } : {}),
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
  }

  function handleBriefingSaved(saved: AiInsight, mode: "create" | "update") {
    setAiEntries((prev) => {
      const current = prev ?? { briefings: [], debriefs: [], commitments: [] };
      return {
        ...current,
        briefings:
          mode === "create"
            ? [saved, ...current.briefings.filter((item) => item.id !== saved.id)]
            : current.briefings.map((item) => (item.id === saved.id ? saved : item)),
      };
    });
    setSelectedBriefing((prev) => (!prev || prev.id !== saved.id ? saved : prev));
  }

  return (
    <div style={{ padding: "32px 48px 60px", maxWidth: 1600, ...lightFieldVars }}>
      {showBriefing && deal && (
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
      {debriefActivity && deal && (
        <CrmAiPanel
          key={debriefActivity.id}
          mode="debrief"
          deal={deal}
          activities={activities}
          company={company}
          contacts={contacts}
          token={token}
          triggerActivity={debriefActivity}
          onStageAdvanced={(updated) => {
            setDeal(updated);
            setDebriefActivity(null);
          }}
          onClose={() => setDebriefActivity(null)}
          onStreamComplete={handleDebriefStreamComplete}
          aiEntries={aiEntries}
        />
      )}

      {/* Back */}
      <button
        onClick={onBack}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          background: "transparent",
          border: "none",
          color: c.inkMuted,
          cursor: "pointer",
          fontFamily: fontBody,
          fontSize: 12,
          padding: "4px 8px 4px 0",
          marginBottom: 18,
        }}
      >
        <Icon d="M19 12H5M12 19l-7-7 7-7" size={14} /> 返回客戶
      </button>

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 24,
          marginBottom: 22,
        }}
      >
        <div style={{ flex: 1 }}>
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
                color: c.inkFaint,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
              }}
            >
              DEAL · #{deal.id.slice(0, 8)}
            </span>
            <Chip t={t} tone={deal.funnelStage === WON_STAGE ? "jade" : "accent"} dot>
              {deal.funnelStage}
            </Chip>
          </div>
          <h1
            style={{
              fontFamily: fontHead,
              fontSize: 34,
              fontWeight: 500,
              color: c.ink,
              margin: 0,
              letterSpacing: "0.02em",
            }}
          >
            {companyName}
          </h1>
          <div style={{ fontFamily: fontHead, fontSize: 16, color: c.inkMuted, marginTop: 4 }}>
            {deal.title}
          </div>
          <div
            style={{
              display: "flex",
              gap: 18,
              marginTop: 10,
              fontSize: 13,
              color: c.inkMuted,
            }}
          >
            <span>
              金額 ·{" "}
              <span style={{ color: c.ink, fontFamily: fontMono }}>
                {fmtAmount(deal.amountTwd)}
              </span>
            </span>
            <span>
              負責 · <span style={{ color: c.ink }}>{deal.ownerPartnerId ?? "—"}</span>
            </span>
            {deal.expectedCloseDate && (
              <span>
                預計結案 ·{" "}
                <span style={{ color: c.ink, fontFamily: fontMono }}>
                  {fmtDate(deal.expectedCloseDate)}
                </span>
              </span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
            <Btn t={t} variant="ghost" size="sm" icon={ICONS.clock} disabled>
              排程
            </Btn>
          <Btn
            t={t}
            variant="outline"
            size="sm"
            icon={ICONS.spark}
            onClick={() => {
              setSelectedBriefing(null);
              setDebriefActivity(null);
              setShowBriefing(true);
            }}
          >
            準備下次會議
          </Btn>
          <Btn
            t={t}
            variant="ink"
            size="sm"
            icon={ICONS.arrow}
            onClick={canAdvance ? handleAdvanceStage : undefined}
            style={canAdvance ? undefined : { opacity: 0.5, cursor: "not-allowed" }}
          >
            {advancing ? "更新中…" : "推進階段"}
          </Btn>
        </div>
      </div>

      {/* Pipeline progress breadcrumb */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "12px 16px",
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          marginBottom: 20,
        }}
      >
        {allStages.map((s, i) => {
          const done = i < curStageIdx;
          const cur = i === curStageIdx;
          return (
            <React.Fragment key={s}>
              <div
                style={{
                  padding: "4px 10px",
                  fontFamily: fontBody,
                  fontSize: 12,
                  color: cur ? c.vermillion : done ? c.ink : c.inkFaint,
                  fontWeight: cur ? 500 : 400,
                  letterSpacing: "0.04em",
                }}
              >
                {s}
              </div>
              {i < allStages.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: 2,
                    background: done ? c.ink : c.inkHair,
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 20,
          borderBottom: `1px solid ${c.inkHair}`,
        }}
      >
        {(
          [
            ["overview", "總覽"],
            ["activity", "活動"],
            ["commits", "承諾事項"],
            ["files", "附件"],
          ] as [typeof tab, string][]
        ).map(([k, l]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            style={{
              padding: "10px 18px",
              background: "transparent",
              border: "none",
              borderBottom:
                tab === k
                  ? `2px solid ${c.vermillion}`
                  : "2px solid transparent",
              marginBottom: -1,
              cursor: "pointer",
              fontFamily: fontBody,
              fontSize: 13,
              color: tab === k ? c.ink : c.inkMuted,
              fontWeight: tab === k ? 500 : 400,
              letterSpacing: "0.04em",
            }}
          >
            {l}
          </button>
        ))}
      </div>

      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          padding: "16px 18px",
          marginBottom: 18,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 18,
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 260, flex: 1 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 6,
            }}
          >
            <Icon d={ICONS.spark} size={13} style={{ color: c.vermillion }} />
            <span
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
              }}
            >
              AI 會議準備
            </span>
          </div>
          <div
            style={{
              fontSize: 13,
              color: c.ink,
              lineHeight: 1.65,
            }}
          >
            {latestBriefing
              ? "可直接延續上一份 briefing 繼續討論，不用切回總覽。"
              : "從這裡直接開 AI 討論，整理下次會議重點與提問策略。"}
          </div>
          <div
            style={{
              marginTop: 6,
              fontSize: 12,
              color: c.inkMuted,
              lineHeight: 1.6,
            }}
          >
            {latestBriefing
              ? `最近一份 briefing：${fmtDate(new Date(latestBriefing.createdAt))}`
              : "新增會議 / Demo / 電話活動後，也會自動觸發 debrief。"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {showBriefing && (
            <Btn
              t={t}
              variant="ghost"
              size="sm"
              onClick={() => setShowBriefing(false)}
            >
              收起 AI 面板
            </Btn>
          )}
          <Btn
            t={t}
            variant="outline"
            size="sm"
            icon={ICONS.spark}
            onClick={() => {
              setSelectedBriefing(latestBriefing);
              setDebriefActivity(null);
              setShowBriefing(true);
            }}
          >
            {latestBriefing ? "繼續 AI 討論" : "開始 AI 討論"}
          </Btn>
        </div>
      </div>

      {/* Content */}
      {tab === "overview" && (
        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}
        >
          {/* Main */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Agent debrief */}
            <div
              style={{
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                padding: 20,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <Icon
                  d={ICONS.spark}
                  size={13}
                  style={{ color: c.vermillion }}
                />
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.2em",
                    textTransform: "uppercase",
                  }}
                >
                  Agent 複盤摘要
                </span>
                <span style={{ flex: 1 }} />
                <Btn
                  t={t}
                  variant="outline"
                  size="sm"
                  icon={ICONS.spark}
                  onClick={() => {
                    setSelectedBriefing(latestBriefing);
                    setDebriefActivity(null);
                    setShowBriefing(true);
                  }}
                >
                  {latestBriefing ? "繼續討論" : "開始 briefing"}
                </Btn>
                <span style={{ width: 6 }} />
                {latestBriefing && (
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: c.inkFaint,
                    }}
                  >
                    {fmtDate(new Date(latestBriefing.createdAt))}
                  </span>
                )}
              </div>

              {latestBriefing ? (
                <div>
                  <div
                    style={{
                      fontSize: 12.5,
                      color: c.inkSoft,
                      lineHeight: 1.8,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {latestBriefing.content}
                  </div>
                  {latestBriefing.metadata != null &&
                    typeof latestBriefing.metadata === "object" &&
                    Boolean((latestBriefing.metadata as Record<string, unknown>).stage_suggestion) && (
                      <div
                        style={{
                          marginTop: 14,
                          padding: "10px 12px",
                          background: c.vermSoft,
                          border: `1px solid ${c.vermLine}`,
                          borderRadius: 2,
                          fontSize: 12.5,
                          color: c.ink,
                          lineHeight: 1.6,
                        }}
                      >
                        <span
                          style={{
                            fontFamily: fontMono,
                            fontSize: 9,
                            color: c.vermillion,
                            letterSpacing: "0.16em",
                            marginRight: 8,
                          }}
                        >
                          階段建議
                        </span>
                        {String(
                          (latestBriefing.metadata as Record<string, unknown>)
                            .stage_suggestion
                        )}
                      </div>
                    )}
                </div>
              ) : (
                <div
                  style={{
                    padding: "20px 0",
                    textAlign: "center",
                    fontSize: 12,
                    color: c.inkFaint,
                  }}
                >
                  尚未產生複盤 · —
                </div>
              )}
            </div>

            {/* Activity timeline */}
            <div
              style={{
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                padding: 20,
              }}
            >
              <div
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  marginBottom: 14,
                }}
              >
                Activity · 近期動態
              </div>
              {activities.length === 0 ? (
                <div
                  style={{
                    padding: "16px 0",
                    textAlign: "center",
                    fontSize: 12,
                    color: c.inkFaint,
                  }}
                >
                  尚無活動記錄 · —
                </div>
              ) : (
                activities.slice(0, 8).map((a, i) => (
                  <div
                    key={a.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "110px 8px 1fr 80px",
                      gap: 12,
                      alignItems: "flex-start",
                      padding: "11px 0",
                      borderBottom:
                        i < Math.min(activities.length, 8) - 1
                          ? `1px solid ${c.inkHair}`
                          : "none",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: c.inkFaint,
                        letterSpacing: "0.08em",
                        paddingTop: 3,
                      }}
                    >
                      {fmtDate(a.activityAt)}
                    </span>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: c.ink,
                        marginTop: 6,
                      }}
                    />
                    <span
                      style={{ fontSize: 13, color: c.ink, lineHeight: 1.55 }}
                    >
                      {a.summary || "—"}
                    </span>
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: c.inkMuted,
                        letterSpacing: "0.08em",
                        textAlign: "right",
                        paddingTop: 3,
                      }}
                    >
                      {a.activityType}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Commitments */}
            <div
              style={{
                background: c.paperWarm,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                padding: 18,
              }}
            >
              <div
                style={{
                  fontFamily: fontHead,
                  fontSize: 13,
                  color: c.ink,
                  fontWeight: 500,
                  marginBottom: 12,
                  letterSpacing: "0.04em",
                }}
              >
                承諾事項
              </div>
              {commitments.length === 0 ? (
                <div
                  style={{ fontSize: 12, color: c.inkFaint, padding: "8px 0" }}
                >
                  —
                </div>
              ) : (
                commitments.map((cm, i) => (
                  <div
                    key={cm.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "6px 0",
                      borderBottom:
                        i < commitments.length - 1
                          ? `1px solid ${c.inkHair}`
                          : "none",
                      fontSize: 12,
                    }}
                  >
                    <span style={{ color: c.ink, flex: 1, marginRight: 8 }}>
                      {cm.content}
                    </span>
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: cm.status === "done" ? c.jade : c.vermillion,
                        flexShrink: 0,
                      }}
                    >
                      {cm.status === "done" ? "完成" : "待辦"}
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* Contacts (from deal.notes if no direct contacts API) */}
            <div
              style={{
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                padding: 18,
              }}
            >
              <div
                style={{
                  fontFamily: fontHead,
                  fontSize: 13,
                  color: c.ink,
                  fontWeight: 500,
                  marginBottom: 12,
                  letterSpacing: "0.04em",
                }}
              >
                聯絡人
              </div>
              <div style={{ fontSize: 12, color: c.inkFaint }}>
                <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
                  {contacts.length === 0
                    ? "—"
                    : contacts.map((contact) => `${contact.name}${contact.title ? ` · ${contact.title}` : ""}`).join("\n")}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "activity" && (
        <div
          style={{
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            padding: 20,
          }}
        >
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              marginBottom: 14,
            }}
          >
            Activity · 所有動態
          </div>
          {recordedBy && deal && (
            <div style={{ marginBottom: 16 }}>
              <InkNewActivityForm
                dealId={deal.id}
                userToken={userToken}
                recordedBy={recordedBy}
                onCreated={handleActivityCreated}
              />
            </div>
          )}
          {activities.length === 0 ? (
            <div
              style={{
                padding: "20px 0",
                textAlign: "center",
                fontSize: 12,
                color: c.inkFaint,
              }}
            >
              尚無活動記錄 · —
            </div>
          ) : (
            activities.map((a, i) => (
              <div
                key={a.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "110px 8px 1fr 80px",
                  gap: 12,
                  alignItems: "flex-start",
                  padding: "11px 0",
                  borderBottom:
                    i < activities.length - 1
                      ? `1px solid ${c.inkHair}`
                      : "none",
                }}
              >
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.08em",
                    paddingTop: 3,
                  }}
                >
                  {fmtDate(a.activityAt)}
                </span>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: c.ink,
                    marginTop: 6,
                  }}
                />
                <span style={{ fontSize: 13, color: c.ink, lineHeight: 1.55 }}>
                  {a.summary || "—"}
                </span>
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkMuted,
                    letterSpacing: "0.08em",
                    textAlign: "right",
                    paddingTop: 3,
                  }}
                >
                  {a.activityType}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "commits" && (
        <div
          style={{
            background: c.paperWarm,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            padding: 20,
          }}
        >
          <div
            style={{
              fontFamily: fontHead,
              fontSize: 13,
              color: c.ink,
              fontWeight: 500,
              marginBottom: 16,
            }}
          >
            承諾事項
          </div>
          {commitments.length === 0 ? (
            <div style={{ fontSize: 12, color: c.inkFaint }}>—</div>
          ) : (
            commitments.map((cm, i) => (
              <div
                key={cm.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "8px 0",
                  borderBottom:
                    i < commitments.length - 1
                      ? `1px solid ${c.inkHair}`
                      : "none",
                  fontSize: 13,
                }}
              >
                <span style={{ color: c.ink, flex: 1, marginRight: 12 }}>
                  {cm.content}
                </span>
                <span
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: cm.status === "done" ? c.jade : c.vermillion,
                  }}
                >
                  {cm.status === "done" ? "完成" : "待辦"}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "files" && (
        <div
          style={{
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            padding: 20,
            textAlign: "center",
            fontSize: 12,
            color: c.inkFaint,
          }}
        >
          附件功能尚未開放 · —
        </div>
      )}
    </div>
  );
}

// ─── Clients list ─────────────────────────────────────────────────────────────

interface ClientsListProps {
  deals: Deal[];
  companiesMap: Record<string, string>;
  onOpen: (id: string) => void;
}

function InkNewActivityForm({
  dealId,
  userToken,
  recordedBy,
  onCreated,
}: {
  dealId: string;
  userToken: () => Promise<string>;
  recordedBy: string;
  onCreated: (activity: Activity) => void;
}) {
  const t = useInk("light");
  const { c, fontBody } = t;
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
  const [activityType, setActivityType] = useState<ActivityType>("會議");
  const [summary, setSummary] = useState("");
  const [activityAt, setActivityAt] = useState(new Date().toISOString().slice(0, 16));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const token = await userToken();
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
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        background: c.paperWarm,
        border: `1px solid ${c.inkHair}`,
        borderRadius: 2,
        padding: 18,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        ...lightFieldVars,
      }}
    >
      <div
        style={{
          fontFamily: fontBody,
          fontSize: 13,
          color: c.ink,
          fontWeight: 500,
          letterSpacing: "0.04em",
        }}
      >
        新增活動
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "180px 220px", gap: 8 }}>
        <select
          value={activityType}
          onChange={(e) => setActivityType(e.target.value as ActivityType)}
          style={{
            padding: "8px 12px",
            background: c.paper,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            fontFamily: fontBody,
            fontSize: 12,
            color: c.ink,
            outline: "none",
          }}
        >
          {["電話", "Email", "會議", "Demo", "備忘"].map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <input
          type="datetime-local"
          value={activityAt}
          onChange={(e) => setActivityAt(e.target.value)}
          style={{
            padding: "8px 12px",
            background: c.paper,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            fontFamily: fontBody,
            fontSize: 12,
            color: c.ink,
            outline: "none",
          }}
        />
      </div>
      <textarea
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="本次互動的重點..."
        rows={4}
        style={{
          width: "100%",
          padding: "8px 12px",
          background: c.paper,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          fontFamily: fontBody,
          fontSize: 12,
          color: c.ink,
          outline: "none",
          resize: "vertical",
          boxSizing: "border-box",
        }}
      />
      {error && <div style={{ fontSize: 11, color: c.vermillion }}>{error}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="submit"
          disabled={saving || !summary.trim()}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "4px 10px",
            fontSize: 11,
            fontFamily: fontBody,
            fontWeight: 500,
            letterSpacing: "0.02em",
            background: saving || !summary.trim() ? c.vermLine : c.vermillion,
            color: "#FFF2EC",
            border: "1px solid transparent",
            borderRadius: 2,
            cursor: saving || !summary.trim() ? "not-allowed" : "pointer",
            opacity: saving || !summary.trim() ? 0.5 : 1,
            transition: "all .15s",
          }}
        >
          {saving ? "建立中…" : "新增活動"}
        </button>
      </div>
    </form>
  );
}

function InkClientsList({
  deals,
  companiesMap,
  onOpen,
  onCreateDeal,
}: ClientsListProps & { onCreateDeal: () => void }) {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;
  const [view, setView] = useState<"pipeline" | "list">("pipeline");

  // KPI
  const totalAmount = deals.reduce((a, d) => a + (d.amountTwd ?? 0), 0);
  const activeDeals = deals.filter(
    (d) => !d.isClosedLost && !d.isOnHold && d.funnelStage !== WON_STAGE
  );
  const wonThisMonth = deals.filter(
    (d) => d.funnelStage === WON_STAGE && d.signedDate && isThisMonth(d.signedDate)
  );
  const avgDeal =
    deals.length > 0 ? Math.round(totalAmount / deals.length / 1000) : 0;

  const kpis = [
    {
      k: "Pipeline 總額",
      v: totalAmount > 0 ? "$" + Math.round(totalAmount / 1000) + "k" : "—",
      sub: deals.length + " 個機會",
    },
    {
      k: "進行中",
      v: activeDeals.length > 0 ? String(activeDeals.length) : "—",
      sub: "活躍商機",
    },
    {
      k: "本月成交",
      v: wonThisMonth.length > 0 ? String(wonThisMonth.length) : "—",
      sub: "結案",
    },
    {
      k: "平均交易",
      v: avgDeal > 0 ? "$" + avgDeal + "k" : "—",
      sub: "每案均值",
    },
  ];

  // Deals by stage (only active stages in pipeline view)
  function dealsByStage(stage: FunnelStage): Deal[] {
    return deals.filter((d) => d.funnelStage === stage && !d.isClosedLost && !d.isOnHold);
  }

  // Stage chip tone
  function stageTone(stage: FunnelStage): "jade" | "accent" | "muted" {
    if (stage === WON_STAGE) return "jade";
    const idx = FUNNEL_STAGES.indexOf(stage);
    if (idx >= FUNNEL_STAGES.length - 2) return "accent";
    return "muted";
  }

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section
        t={t}
        eyebrow="CRM · 客戶"
        title="客戶"
        en="Clients"
        subtitle="所有銷售機會與聯絡人，支援 Pipeline 與列表檢視。"
        right={
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
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
                  ["pipeline", "Pipeline"],
                  ["list", "列表"],
                ] as [string, string][]
              ).map(([k, l]) => (
                <button
                  key={k}
                  onClick={() => setView(k as "pipeline" | "list")}
                  style={{
                    padding: "5px 12px",
                    background: view === k ? c.ink : "transparent",
                    color: view === k ? c.paper : c.inkMuted,
                    border: "none",
                    borderRadius: 2,
                    cursor: "pointer",
                    fontFamily: fontBody,
                    fontSize: 12,
                    letterSpacing: "0.04em",
                  }}
                >
                  {l}
                </button>
              ))}
            </div>
            <Btn t={t} variant="ghost" icon={ICONS.filter} disabled>
              篩選
            </Btn>
            <Btn t={t} variant="seal" icon={ICONS.plus} onClick={onCreateDeal}>
              新機會
            </Btn>
          </div>
        }
      />

      {/* KPI strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 1,
          background: c.inkHair,
          border: `1px solid ${c.inkHair}`,
          marginBottom: 24,
        }}
      >
        {kpis.map((s, i) => (
          <div key={i} style={{ background: c.surface, padding: "16px 18px" }}>
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
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>
              {s.sub}
            </div>
          </div>
        ))}
      </div>

      {view === "pipeline" ? (
        /* Pipeline: 5 columns (active funnel stages only) */
        <div
          style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}
        >
          {FUNNEL_STAGES.map((stage) => {
            const col = dealsByStage(stage);
            const sum = col.reduce((a, d) => a + (d.amountTwd ?? 0), 0);
            return (
              <div
                key={stage}
                style={{ display: "flex", flexDirection: "column", gap: 10 }}
              >
                {/* Column header */}
                <div
                  style={{
                    padding: "10px 12px",
                    background: c.surface,
                    border: `1px solid ${c.inkHair}`,
                    borderRadius: 2,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "baseline",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: fontHead,
                        fontSize: 13,
                        fontWeight: 500,
                        color: c.ink,
                        letterSpacing: "0.04em",
                      }}
                    >
                      {stage}
                    </span>
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: c.inkFaint,
                      }}
                    >
                      {col.length}
                    </span>
                  </div>
                  <div
                    style={{
                      fontFamily: fontMono,
                      fontSize: 10,
                      color: c.inkFaint,
                      letterSpacing: "0.12em",
                      marginTop: 3,
                    }}
                  >
                    {sum > 0 ? "$" + Math.round(sum / 1000) + "k" : "—"}
                  </div>
                </div>

                {/* Deal cards */}
                {col.map((d) => {
                  const company = companiesMap[d.companyId] ?? "—";
                  return (
                    <button
                      key={d.id}
                      onClick={() => onOpen(d.id)}
                      style={{
                        padding: "12px 12px",
                        background: c.surface,
                        border: `1px solid ${c.inkHair}`,
                        borderLeft: `1px solid ${c.inkHair}`,
                        borderRadius: 2,
                        textAlign: "left",
                        cursor: "pointer",
                        fontFamily: fontBody,
                        color: c.ink,
                        transition: "all .12s",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.background =
                          c.surfaceHi;
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.background =
                          c.surface;
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "baseline",
                          marginBottom: 4,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 13,
                            fontWeight: 500,
                            letterSpacing: "0.02em",
                          }}
                        >
                          {company}
                        </span>
                      </div>
                      <div
                        style={{
                          fontFamily: fontHead,
                          fontSize: 14,
                          fontWeight: 500,
                          color: c.inkMuted,
                          letterSpacing: "0.02em",
                          marginBottom: 4,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {d.title}
                      </div>
                      <div
                        style={{
                          fontFamily: fontHead,
                          fontSize: 16,
                          fontWeight: 500,
                          color: c.ink,
                          letterSpacing: "0.02em",
                        }}
                      >
                        {fmtAmount(d.amountTwd)}
                      </div>
                      {d.expectedCloseDate && (
                        <div
                          style={{
                            fontFamily: fontMono,
                            fontSize: 10,
                            color: c.inkFaint,
                            marginTop: 6,
                            letterSpacing: "0.04em",
                          }}
                        >
                          截止 {fmtDate(d.expectedCloseDate)}
                        </div>
                      )}
                    </button>
                  );
                })}

                {col.length === 0 && (
                  <div
                    style={{
                      padding: 16,
                      background: "transparent",
                      border: `1px dashed ${c.inkHair}`,
                      borderRadius: 2,
                      textAlign: "center",
                      fontSize: 11,
                      color: c.inkFaint,
                    }}
                  >
                    空
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        /* List view */
        <div
          style={{
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 160px 100px 120px 160px",
              gap: 12,
              padding: "10px 16px",
              borderBottom: `1px solid ${c.inkHairBold}`,
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            <span>公司 · 商機</span>
            <span>階段</span>
            <span>金額</span>
            <span>負責</span>
            <span>預計結案</span>
          </div>
          {deals
            .filter((d) => !d.isClosedLost && !d.isOnHold)
            .map((d) => {
              const company = companiesMap[d.companyId] ?? "—";
              return (
                <button
                  key={d.id}
                  onClick={() => onOpen(d.id)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 160px 100px 120px 160px",
                    gap: 12,
                    alignItems: "center",
                    width: "100%",
                    padding: "14px 16px",
                    borderBottom: `1px solid ${c.inkHair}`,
                    background: "transparent",
                    border: "none",
                    borderLeft: "2px solid transparent",
                    color: c.ink,
                    cursor: "pointer",
                    textAlign: "left",
                    fontFamily: fontBody,
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background =
                      c.surfaceHi;
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background =
                      "transparent";
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{company}</div>
                    <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>
                      {d.title}
                    </div>
                  </div>
                  <Chip t={t} tone={stageTone(d.funnelStage)} dot>
                    {d.funnelStage}
                  </Chip>
                  <span style={{ fontFamily: fontMono, fontSize: 13, color: c.ink }}>
                    {fmtAmount(d.amountTwd)}
                  </span>
                  <span style={{ fontSize: 12, color: c.inkMuted }}>
                    {d.ownerPartnerId ?? "—"}
                  </span>
                  <span
                    style={{
                      fontFamily: fontMono,
                      fontSize: 11,
                      color: c.inkMuted,
                      letterSpacing: "0.04em",
                    }}
                  >
                    {fmtDate(d.expectedCloseDate)}
                  </span>
                </button>
              );
            })}
          {deals.filter((d) => !d.isClosedLost && !d.isOnHold).length === 0 && (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                fontSize: 12,
                color: c.inkFaint,
              }}
            >
              目前沒有進行中的商機 · —
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Root workspace ───────────────────────────────────────────────────────────

export default function ZenInkClientsWorkspace() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const { isHomeWorkspace } = resolveActiveWorkspace(partner);

  const [deals, setDeals] = useState<Deal[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Route guard — same as ClientsWorkspace
  useEffect(() => {
    if (partner && !isHomeWorkspace) {
      router.replace("/tasks");
    }
  }, [isHomeWorkspace, partner, router]);

  const userToken = useCallback(async (): Promise<string> => {
    if (!user) throw new Error("Not authenticated");
    return user.getIdToken();
  }, [user]);

  const load = useCallback(async () => {
    if (!user || !partner) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const [fetchedDeals, fetchedCompanies] = await Promise.all([
        getDeals(token),
        getCompanies(token),
      ]);
      setDeals(fetchedDeals);
      setCompanies(fetchedCompanies);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入客戶資料");
    } finally {
      setLoading(false);
    }
  }, [partner, user]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDealCreated = useCallback((newDeal: Deal, newCompany?: Company) => {
    if (newCompany) {
      setCompanies((prev) => [...prev, newCompany]);
    }
    setDeals((prev) => [newDeal, ...prev]);
  }, []);

  // Render nothing while redirecting shared-workspace users
  if (partner && !isHomeWorkspace) return null;

  const companiesMap = Object.fromEntries(
    companies.map((c) => [c.id, c.name])
  );

  if (loading) return <InkSpinner message="載入客戶資料..." />;
  if (error) return <InkErrorCard message={error} onRetry={load} />;

  if (openId) {
    return (
      <InkDealDetail
        dealId={openId}
        companiesMap={companiesMap}
        onBack={() => setOpenId(null)}
        userToken={userToken}
        recordedBy={partner?.id ?? null}
      />
    );
  }

  return (
    <>
      <InkClientsList deals={deals} companiesMap={companiesMap} onOpen={setOpenId} onCreateDeal={() => setIsModalOpen(true)} />
      <NewDealModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        companies={companies}
        onCreated={handleDealCreated}
        user={user}
        userId={partner?.id ?? ""}
      />
    </>
  );
}
