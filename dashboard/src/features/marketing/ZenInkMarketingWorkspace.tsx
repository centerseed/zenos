"use client";

// ZenOS · Marketing — Zen Ink visual wired to marketing-api
// S04 real-data wiring: getMarketingProjectGroups / getMarketingProjectDetail /
//   getMarketingProjectStyles / updateMarketingProjectStrategy /
//   createMarketingStyle / updateMarketingStyle

import { Fragment, useCallback, useEffect, useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Btn } from "@/components/zen/Btn";
import { Chip } from "@/components/zen/Chip";
import { Section } from "@/components/zen/Section";
import { useAuth } from "@/lib/auth";
import { CoworkChatSheet, PromptManagerSheet } from "@/features/marketing/MarketingWorkspace";
import {
  buildProjectSummary,
  formatContentMix,
  formatCsv,
  parseContentMix,
  parseCsv,
  type FieldDiscussionConfig,
  type PromptDraftDiscussionConfig,
} from "@/features/marketing/logic";
import { normalizeSourceCitations } from "@/lib/cowork-knowledge";
import {
  getMarketingProjectGroups,
  getMarketingProjectDetail,
  getMarketingProjectStyles,
  updateMarketingProjectStrategy,
  createMarketingStyle,
  updateMarketingStyle,
} from "@/lib/marketing-api";
import type {
  MarketingProject,
  MarketingProjectGroup,
  MarketingStyle,
  MarketingStyleBuckets,
} from "@/lib/marketing-api";

// ─── Constants ────────────────────────────────────────────────────────────────

const MKT_STAGES = ["策略", "排程", "情報", "生成", "確認", "發佈"];

const ARROW_LEFT = "M19 12H5M12 19l-7-7 7-7";

// ─── Types ────────────────────────────────────────────────────────────────────

type ZenMktStatus = "drafting" | "in_review" | "approved";
type ZenStatusTone = "muted" | "ocher" | "jade";

interface ZenStatusInfo {
  tone: ZenStatusTone;
  label: string;
}

function getStrategySaveBlockers(input: {
  projectType: MarketingProject["projectType"];
  audience: string[];
  tone: string;
  coreMessage: string;
  platforms: string[];
  frequency?: string;
  contentMix?: Record<string, number>;
}) {
  const blockers: string[] = [];
  if (input.audience.length === 0) blockers.push("目標受眾");
  if (!input.tone.trim()) blockers.push("語氣風格");
  if (!input.coreMessage.trim()) blockers.push("核心訊息");
  if (input.platforms.length === 0) blockers.push("發文平台");
  if (input.projectType === "long_term") {
    if (!input.frequency?.trim()) blockers.push("發文頻率");
    if (!input.contentMix || Object.keys(input.contentMix).length === 0) blockers.push("內容比例");
  }
  return blockers;
}

// Map MarketingProject.status to Zen Ink display status
function toZenStatus(status: MarketingProject["status"]): ZenMktStatus {
  switch (status) {
    case "active":
      return "drafting";
    case "blocked":
      return "in_review";
    case "completed":
      return "approved";
    default:
      return "drafting";
  }
}

const ZEN_STATUS_MAP: Record<ZenMktStatus, ZenStatusInfo> = {
  drafting: { tone: "muted", label: "撰寫中" },
  in_review: { tone: "ocher", label: "審查中" },
  approved: { tone: "jade", label: "已核准" },
};

// Derive stage index (0–5) from project data
function deriveStageIndex(project: MarketingProject): number {
  if (project.status === "completed") return 5;
  const strategy = project.strategy;
  if (!strategy) return 0;
  const contentPlan = project.contentPlan;
  if (!contentPlan || contentPlan.length === 0) return 1;
  const posts = project.posts ?? [];
  if (posts.length === 0) return 2;
  const hasDraft = posts.some((p) => p.status === "draft_generated" || p.status === "draft_confirmed");
  if (!hasDraft) return 3;
  const allConfirmed = posts.every((p) =>
    ["draft_confirmed", "platform_confirmed", "scheduled", "published"].includes(p.status)
  );
  if (!allConfirmed) return 4;
  return 5;
}

// Flatten groups → campaign array with group context
interface Campaign {
  project: MarketingProject;
  groupName: string;
  stageIndex: number;
  zenStatus: ZenMktStatus;
}

function flattenGroups(groups: MarketingProjectGroup[]): Campaign[] {
  const result: Campaign[] = [];
  for (const g of groups) {
    for (const p of g.projects) {
      result.push({
        project: p,
        groupName: g.product.name,
        stageIndex: deriveStageIndex(p),
        zenStatus: toZenStatus(p.status),
      });
    }
  }
  return result;
}

// ─── Loading / Error states ───────────────────────────────────────────────────

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
      <span style={{ fontFamily: fontMono, fontSize: 12, color: c.inkMuted, letterSpacing: "0.1em" }}>
        {message}
      </span>
    </div>
  );
}

function InkErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
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
        <p style={{ fontSize: 13, color: c.ink, margin: 0, lineHeight: 1.6 }}>{message}</p>
        <Btn t={t} variant="outline" onClick={onRetry}>
          重試
        </Btn>
      </div>
    </div>
  );
}

// ─── Campaign List ────────────────────────────────────────────────────────────

interface ListProps {
  campaigns: Campaign[];
  loading: boolean;
  onOpen: (id: string) => void;
  onNewCampaign: () => void;
}

function InkMktList({ campaigns, loading, onOpen, onNewCampaign }: ListProps) {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;

  const inProgressCount = campaigns.filter(
    (cam) => cam.zenStatus === "drafting" || cam.zenStatus === "in_review"
  ).length;

  const kpiItems = [
    { k: "進行中", v: loading ? "…" : String(inProgressCount), sub: "—" },
    { k: "本月觸及", v: "—", sub: "—" },
    { k: "轉換率", v: "—", sub: "—" },
    { k: "Agent 草稿", v: "—", sub: "—" },
  ];

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section
        t={t}
        eyebrow="GROWTH · 行銷"
        title="行銷"
        en="Marketing"
        subtitle="與 Agent 共筆文案、品牌聲音與素材；一個地方管理所有渠道。"
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <Btn t={t} variant="ghost" icon={ICONS.doc}>品牌手冊</Btn>
            <Btn t={t} variant="outline" icon={ICONS.spark}>Agent 寫一則</Btn>
            <Btn t={t} variant="seal" icon={ICONS.plus} onClick={onNewCampaign}>新 Campaign</Btn>
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
        {kpiItems.map((s, i) => (
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
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Campaigns table */}
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
            padding: "12px 16px",
            borderBottom: `1px solid ${c.inkHair}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              fontFamily: fontHead,
              fontSize: 14,
              fontWeight: 500,
              color: c.ink,
              letterSpacing: "0.04em",
            }}
          >
            Campaigns
          </span>
          <span
            style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.12em" }}
          >
            {loading ? "…" : `${campaigns.length} ITEMS`}
          </span>
        </div>

        {/* Empty state */}
        {!loading && campaigns.length === 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              minHeight: 120,
              color: c.inkFaint,
              fontFamily: fontMono,
              fontSize: 13,
              letterSpacing: "0.08em",
            }}
          >
            目前沒有 Campaign
          </div>
        )}

        {campaigns.map((cam, i) => {
          const st = ZEN_STATUS_MAP[cam.zenStatus];
          const project = cam.project;
          const channel = project.description
            ? project.description.slice(0, 20)
            : "—";
          const dueLabel = project.dateRange?.end
            ? project.dateRange.end.slice(5).replace("-", "/")
            : "—";

          return (
            <button
              key={project.id}
              onClick={() => onOpen(project.id)}
              style={{
                display: "grid",
                gridTemplateColumns: "24px 1fr 140px 90px 90px",
                alignItems: "center",
                gap: 12,
                padding: "14px 16px",
                width: "100%",
                background: "transparent",
                border: "none",
                borderLeft: "2px solid transparent",
                borderBottom: `1px solid ${c.inkHair}`,
                color: c.ink,
                cursor: "pointer",
                textAlign: "left",
                fontFamily: fontBody,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = c.surfaceHi;
                e.currentTarget.style.borderLeftColor = c.vermillion;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.borderLeftColor = "transparent";
              }}
            >
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  letterSpacing: "0.08em",
                }}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <div
                  style={{
                    fontSize: 14,
                    color: c.ink,
                    fontWeight: 500,
                    letterSpacing: "0.02em",
                  }}
                >
                  {project.name}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: c.inkMuted,
                    marginTop: 3,
                    display: "flex",
                    gap: 8,
                  }}
                >
                  <span>{cam.groupName}</span>
                  <span style={{ color: c.inkFaint }}>·</span>
                  <span style={{ fontFamily: fontMono }}>{dueLabel}</span>
                </div>
              </div>
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkMuted,
                  letterSpacing: "0.08em",
                }}
              >
                階段 · {MKT_STAGES[cam.stageIndex] ?? "—"}
              </span>
              {/* Performance bar — no data, show placeholder */}
              <div>
                <div
                  style={{
                    height: 3,
                    background: c.inkHair,
                    position: "relative",
                    overflow: "hidden",
                  }}
                >
                  <div style={{ position: "absolute", inset: 0, width: "0%", background: c.inkFaint }} />
                </div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 9,
                    color: c.inkFaint,
                    marginTop: 3,
                    textAlign: "right",
                  }}
                >
                  —
                </div>
              </div>
              <Chip t={t} tone={st.tone} dot style={{ justifySelf: "start" }}>
                {st.label}
              </Chip>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Campaign Detail ──────────────────────────────────────────────────────────

interface DetailViewProps {
  projectId: string;
  onBack: () => void;
}

function InkMktDetail({ projectId, onBack }: DetailViewProps) {
  const t = useInk("light");
  const { c, fontHead, fontMono, fontBody } = t;
  const { user } = useAuth();

  const [project, setProject] = useState<MarketingProject | null>(null);
  const [styles, setStyles] = useState<MarketingStyleBuckets>({ product: [], platform: [], project: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [stage, setStage] = useState<number>(0);

  // Strategy save state
  const [strategyText, setStrategyText] = useState("");
  const [savingStrategy, setSavingStrategy] = useState(false);
  const [strategyError, setStrategyError] = useState<string | null>(null);

  // Style add form
  const [newStyleTitle, setNewStyleTitle] = useState("");
  const [newStyleLevel, setNewStyleLevel] = useState<"product" | "platform" | "project">("project");
  const [addingStyle, setAddingStyle] = useState(false);

  // Style edit state: map from styleId → { title, content } being edited
  const [editingStyles, setEditingStyles] = useState<Record<string, { title: string; content: string }>>({});
  const [savingStyleId, setSavingStyleId] = useState<string | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [activeFieldContext, setActiveFieldContext] = useState<FieldDiscussionConfig | undefined>();
  const [activePromptContext, setActivePromptContext] = useState<PromptDraftDiscussionConfig | undefined>();

  const fetchDetail = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const [proj, styleData] = await Promise.all([
        getMarketingProjectDetail(token, projectId),
        getMarketingProjectStyles(token, projectId),
      ]);
      setProject(proj);
      setStyles(styleData);
      if (proj) {
        const idx = deriveStageIndex(proj);
        setStage(idx);
        // Pre-fill strategy textarea from existing strategy
        const existing = proj.strategy;
        if (existing) {
          setStrategyText(
            [
              existing.coreMessage ? `核心訊息：${existing.coreMessage}` : "",
              existing.campaignGoal ? `目標：${existing.campaignGoal}` : "",
              existing.tone ? `語調：${existing.tone}` : "",
            ]
              .filter(Boolean)
              .join("\n")
          );
        }
      }
    } catch (err) {
      console.error("[ZenInkMktDetail] fetch failed:", err);
      setError(err instanceof Error ? err.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [user, projectId]);

  useEffect(() => {
    void fetchDetail();
  }, [fetchDetail]);

  const handleOpenFieldCopilot = useCallback((config: FieldDiscussionConfig) => {
    setActivePromptContext(undefined);
    setActiveFieldContext(config);
    setCopilotOpen(true);
  }, []);

  const handleOpenPromptCopilot = useCallback((config: PromptDraftDiscussionConfig) => {
    setActiveFieldContext(undefined);
    setActivePromptContext(config);
    setCopilotOpen(true);
  }, []);

  // ── Strategy save ───────────────────────────────────────────────────────────

  const handleSaveStrategy = useCallback(async () => {
    if (!user || !project) return;
    setSavingStrategy(true);
    setStrategyError(null);
    try {
      const token = await user.getIdToken();
      const updated = await updateMarketingProjectStrategy(token, project.id, {
        audience: project.strategy?.audience ?? [],
        tone: project.strategy?.tone ?? "",
        coreMessage: strategyText,
        platforms: project.strategy?.platforms ?? [],
      });
      setProject(updated);
    } catch (err) {
      console.error("[ZenInkMktDetail] strategy save failed:", err);
      setStrategyError(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSavingStrategy(false);
    }
  }, [user, project, strategyText]);

  const handleApplyStrategy = useCallback(
    async (payload: { targetField: string; value: unknown }) => {
      if (!user || !project) return;
      if (payload.targetField !== "strategy" || !payload.value || typeof payload.value !== "object") {
        throw new Error("AI 輸出的 strategy 結構不正確");
      }
      const record = payload.value as Record<string, unknown>;
      const nextAudience = Array.isArray(record.audience) ? record.audience.map(String) : parseCsv(String(record.audience || ""));
      const nextTone = String(record.tone || "").trim();
      const nextCoreMessage = String(record.core_message || record.coreMessage || "").trim();
      const nextPlatforms = Array.isArray(record.platforms) ? record.platforms.map(String) : parseCsv(String(record.platforms || ""));
      const nextFrequency = String(record.frequency || "").trim();
      const nextContentMix = parseContentMix(JSON.stringify(record.content_mix || record.contentMix || {}));
      const nextCampaignGoal = String(record.campaign_goal || record.campaignGoal || "").trim();
      const nextCtaStrategy = String(record.cta_strategy || record.ctaStrategy || "").trim();
      const referenceMaterialsRaw = record.reference_materials ?? record.referenceMaterials;
      const nextReferenceMaterials = Array.isArray(referenceMaterialsRaw)
        ? referenceMaterialsRaw.map(String)
        : parseCsv(String(record.reference_materials || record.referenceMaterials || ""));
      const pendingFieldsRaw = record.pending_fields ?? record.pendingFields;
      const nextPendingFields = Array.isArray(pendingFieldsRaw) ? pendingFieldsRaw.map(String).filter(Boolean) : [];
      const sourceCitations = normalizeSourceCitations(record.source_citations ?? record.sourceCitations);
      const confidenceRaw = String(record.confidence || "").trim().toLowerCase();
      const confidence = confidenceRaw === "low" || confidenceRaw === "medium" || confidenceRaw === "high" ? confidenceRaw : undefined;
      const nextSaveBlockers = getStrategySaveBlockers({
        projectType: project.projectType,
        audience: nextAudience,
        tone: nextTone,
        coreMessage: nextCoreMessage,
        platforms: nextPlatforms,
        frequency: nextFrequency,
        contentMix: nextContentMix,
      });
      if (nextSaveBlockers.length > 0) {
        throw new Error(`還缺 ${nextSaveBlockers.join("、")}，補完後才能儲存策略。`);
      }

      const token = await user.getIdToken();
      const updated = await updateMarketingProjectStrategy(token, project.id, {
        audience: nextAudience,
        tone: nextTone,
        coreMessage: nextCoreMessage,
        platforms: nextPlatforms,
        frequency: project.projectType === "long_term" ? nextFrequency : undefined,
        contentMix: project.projectType === "long_term" ? nextContentMix : undefined,
        campaignGoal: nextCampaignGoal,
        ctaStrategy: nextCtaStrategy,
        referenceMaterials: nextReferenceMaterials,
        pendingFields: nextPendingFields,
        sourceCitations,
        confidence,
        expectedUpdatedAt: project.strategy?.updatedAt,
      });
      setProject(updated);
      setStrategyText(
        [
          nextCoreMessage ? `核心訊息：${nextCoreMessage}` : "",
          nextCampaignGoal ? `目標：${nextCampaignGoal}` : "",
          nextTone ? `語調：${nextTone}` : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      setStrategyError(null);
    },
    [project, user]
  );

  // ── Style CRUD ──────────────────────────────────────────────────────────────

  const handleAddStyle = useCallback(async () => {
    if (!user || !project || !newStyleTitle.trim()) return;
    setAddingStyle(true);
    try {
      const token = await user.getIdToken();
      const created = await createMarketingStyle(token, {
        title: newStyleTitle.trim(),
        level: newStyleLevel,
        content: "",
        projectId: project.id,
      });
      setStyles((prev) => ({
        ...prev,
        [newStyleLevel]: [...prev[newStyleLevel], created],
      }));
      setNewStyleTitle("");
    } catch (err) {
      console.error("[ZenInkMktDetail] add style failed:", err);
    } finally {
      setAddingStyle(false);
    }
  }, [user, project, newStyleTitle, newStyleLevel]);

  const handleApplyStyle = useCallback(
    async (payload: { targetField: string; value: unknown }) => {
      if (!user || !project) return;
      if (payload.targetField !== "style" || !payload.value || typeof payload.value !== "object") {
        throw new Error("AI 輸出的 style 結構不正確");
      }
      const record = payload.value as Record<string, unknown>;
      const nextTitle = String(record.title || "AI 建議文風").trim();
      const nextLevel = (record.level === "product" || record.level === "platform" || record.level === "project"
        ? record.level
        : "project") as MarketingStyle["level"];
      const nextPlatform = String(record.platform || "").trim();
      const nextContent = String(record.content || "").trim();
      if (!nextContent) {
        throw new Error("AI 尚未給出文風內容");
      }

      const token = await user.getIdToken();
      const editingStyleId = Object.keys(editingStyles)[0] || null;
      if (editingStyleId) {
        const updated = await updateMarketingStyle(token, editingStyleId, {
          title: nextTitle,
          content: nextContent,
        });
        setStyles((prev) => {
          const update = (list: MarketingStyle[]) => list.map((style) => (style.id === editingStyleId ? updated : style));
          return {
            product: update(prev.product),
            platform: update(prev.platform),
            project: update(prev.project),
          };
        });
        setEditingStyles((prev) => {
          const next = { ...prev };
          delete next[editingStyleId];
          return next;
        });
        return;
      }

      const created = await createMarketingStyle(token, {
        title: nextTitle,
        level: nextLevel,
        content: nextContent,
        productId: nextLevel === "project" ? undefined : project.productId || undefined,
        projectId: nextLevel === "project" ? project.id : undefined,
        platform: nextLevel === "platform" ? nextPlatform || undefined : undefined,
      });
      setStyles((prev) => ({
        ...prev,
        [created.level]: [...prev[created.level], created],
      }));
      setNewStyleTitle("");
    },
    [editingStyles, project, user]
  );

  const handleSaveStyle = useCallback(
    async (styleId: string) => {
      if (!user) return;
      const edit = editingStyles[styleId];
      if (!edit) return;
      setSavingStyleId(styleId);
      try {
        const token = await user.getIdToken();
        const updated = await updateMarketingStyle(token, styleId, {
          title: edit.title,
          content: edit.content,
        });
        // Update styles in state
        setStyles((prev) => {
          const update = (list: MarketingStyle[]): MarketingStyle[] =>
            list.map((s) => (s.id === styleId ? updated : s));
          return {
            product: update(prev.product),
            platform: update(prev.platform),
            project: update(prev.project),
          };
        });
        // Clear edit state
        setEditingStyles((prev) => {
          const next = { ...prev };
          delete next[styleId];
          return next;
        });
      } catch (err) {
        console.error("[ZenInkMktDetail] save style failed:", err);
      } finally {
        setSavingStyleId(null);
      }
    },
    [user, editingStyles]
  );

  const startEditStyle = useCallback((s: MarketingStyle) => {
    setEditingStyles((prev) => ({
      ...prev,
      [s.id]: { title: s.title, content: s.content },
    }));
  }, []);

  // ── Loading / Error ─────────────────────────────────────────────────────────

  if (loading) return <InkSpinner message="載入行銷資料…" />;
  if (error) return <InkErrorCard message={error} onRetry={fetchDetail} />;

  const zenStatus = project ? toZenStatus(project.status) : "drafting";
  const st = ZEN_STATUS_MAP[zenStatus];

  // Collect all styles flat for display
  const allStyles: MarketingStyle[] = [
    ...styles.product,
    ...styles.platform,
    ...styles.project,
  ];

  return (
    <div style={{ padding: "32px 48px 60px", maxWidth: 1600 }}>
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
          letterSpacing: "0.02em",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = c.ink)}
        onMouseLeave={(e) => (e.currentTarget.style.color = c.inkMuted)}
      >
        <Icon d={ARROW_LEFT} size={14} />
        返回 Campaigns
      </button>

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 24,
          marginBottom: 28,
        }}
      >
        <div style={{ flex: 1 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 10,
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
              CAMPAIGN · 行銷項目
            </span>
            <Chip t={t} tone={st.tone} dot>
              {st.label}
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
              lineHeight: 1.15,
            }}
          >
            {project?.name ?? "—"}
          </h1>
          <p
            style={{
              fontSize: 13,
              color: c.inkMuted,
              margin: "10px 0 0",
              maxWidth: 700,
              lineHeight: 1.7,
            }}
          >
            {project?.description || "—"}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, paddingTop: 4 }}>
          <PromptManagerSheet
            user={user ? { getIdToken: () => user.getIdToken() } : null}
            onError={(message) => setError(message)}
            onOpenPromptCopilot={handleOpenPromptCopilot}
          />
          <Btn t={t} variant="ghost" size="sm" icon={ICONS.doc}>Brief</Btn>
          <Btn t={t} variant="outline" size="sm" icon={ICONS.link}>分享</Btn>
          <Btn t={t} variant="ink" size="sm" icon={ICONS.check}>標記完成</Btn>
        </div>
      </div>

      {/* 6-Stage Stepper */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "14px 18px",
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: 2,
          marginBottom: 24,
          flexWrap: "wrap",
        }}
      >
        {MKT_STAGES.map((s, i) => {
          const done = i < stage;
          const cur = i === stage;
          return (
            <Fragment key={i}>
              <button
                onClick={() => setStage(i)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "6px 12px",
                  background: cur ? c.vermSoft : "transparent",
                  border: `1px solid ${cur ? c.vermLine : done ? c.inkHair : "transparent"}`,
                  borderRadius: 2,
                  cursor: "pointer",
                  fontFamily: fontBody,
                  fontSize: 12,
                  color: cur ? c.vermillion : done ? c.ink : c.inkFaint,
                  fontWeight: cur ? 500 : 400,
                  letterSpacing: "0.04em",
                  transition: "all .15s",
                }}
              >
                <span
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: "50%",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: cur ? c.vermillion : done ? c.ink : "transparent",
                    border: `1px solid ${cur ? c.vermillion : done ? c.ink : c.inkHair}`,
                    color: cur || done ? c.paper : c.inkFaint,
                    fontFamily: fontMono,
                    fontSize: 9,
                    fontWeight: 600,
                  }}
                >
                  {done ? "✓" : i + 1}
                </span>
                {s}
              </button>
              {i < MKT_STAGES.length - 1 && (
                <div
                  style={{
                    width: 16,
                    height: 1,
                    background: i < stage ? c.ink : c.inkHair,
                  }}
                />
              )}
            </Fragment>
          );
        })}
      </div>

      {/* Content grid: main workareas + AI rail */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Current stage card */}
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
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 14,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: fontMono,
                    fontSize: 10,
                    color: c.inkFaint,
                    letterSpacing: "0.2em",
                    textTransform: "uppercase",
                    marginBottom: 6,
                  }}
                >
                  目前階段 · {MKT_STAGES[stage] ?? "—"}
                </div>
                <div
                  style={{
                    fontFamily: fontHead,
                    fontSize: 18,
                    fontWeight: 500,
                    color: c.ink,
                    letterSpacing: "0.04em",
                  }}
                >
                  {stage === 0 && "定義策略"}
                  {stage === 1 && "建立排程"}
                  {stage === 2 && "蒐集情報"}
                  {stage === 3 && "生成內容"}
                  {stage === 4 && "確認草稿"}
                  {stage === 5 && "發佈完成"}
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: c.inkMuted,
                    marginTop: 6,
                    lineHeight: 1.6,
                  }}
                >
                  {stage === 0 && "先確立目標受眾、語調與核心訊息，再進入排程。"}
                  {stage === 1 && "設定每週/月的發文計畫。"}
                  {stage === 2 && (
                    <>
                      主題已建立。先跑{" "}
                      <code
                        style={{
                          fontFamily: fontMono,
                          fontSize: 11,
                          background: c.paperWarm,
                          padding: "1px 5px",
                          borderRadius: 2,
                        }}
                      >
                        /marketing-intel
                      </code>{" "}
                      蒐集近期訊號。
                    </>
                  )}
                  {stage === 3 && "根據情報與策略，讓 Agent 生成草稿。"}
                  {stage === 4 && "審查草稿，確認後可排程。"}
                  {stage === 5 && "已完成所有發佈流程。"}
                </div>
              </div>
              <Chip t={t} tone="accent" dot>
                目前階段
              </Chip>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["按「帶進 AI」開始", "集中在同一個 AI 工作區討論", "有 structured result 才套用"].map(
                (h, i) => (
                  <Chip key={i} t={t} tone="muted">
                    {h}
                  </Chip>
                )
              )}
            </div>
          </div>

          {/* Strategy + writing plan */}
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
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 12,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: fontHead,
                    fontSize: 15,
                    fontWeight: 500,
                    color: c.ink,
                    letterSpacing: "0.04em",
                  }}
                >
                  建立行銷寫作計畫
                </div>
                <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 4 }}>
                  先和 AI 討論策略，不再由手填一堆欄位。
                </div>
              </div>
              <Btn
                t={t}
                variant="outline"
                size="sm"
                icon={ICONS.spark}
                onClick={() =>
                  handleOpenFieldCopilot({
                    fieldId: "strategy",
                    fieldLabel: "策略設定",
                    currentPhase: "strategy",
                    suggestedSkill: "/marketing-plan",
                    projectSummary: buildProjectSummary(project!),
                    conflictVersion: project?.strategy?.updatedAt || null,
                    conflictLabel: "策略",
                    fieldValue: {
                      audience: project?.strategy?.audience ?? [],
                      tone: project?.strategy?.tone ?? "",
                      core_message: project?.strategy?.coreMessage ?? "",
                      platforms: project?.strategy?.platforms ?? [],
                      frequency: project?.strategy?.frequency ?? "",
                      content_mix: project?.strategy?.contentMix ?? {},
                      campaign_goal: project?.strategy?.campaignGoal ?? "",
                      cta_strategy: project?.strategy?.ctaStrategy ?? "",
                      reference_materials: project?.strategy?.referenceMaterials ?? [],
                    },
                    relatedContext: project?.strategy?.summaryEntry,
                    onApply: handleApplyStrategy,
                  })
                }
              >
                先帶進 AI —
              </Btn>
            </div>
            <div
              style={{
                padding: "11px 14px",
                background: c.paper,
                border: `1px solid ${c.inkHair}`,
                borderRadius: 2,
                fontSize: 12.5,
                color: c.inkMuted,
                fontFamily: fontBody,
                marginBottom: 10,
              }}
            >
              AI 工作區會沿用同一套對話、權限、diff 與寫回流程。策略討論完可直接套用到下方欄位。
            </div>
            <details open style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 12, marginTop: 12 }}>
              <summary
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 12,
                  color: c.ink,
                  cursor: "pointer",
                  fontFamily: fontBody,
                  letterSpacing: "0.02em",
                  listStyle: "none",
                }}
              >
                <Icon d={ICONS.chev} size={12} style={{ color: c.inkFaint }} />
                手動微調策略（進階）
              </summary>
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                <textarea
                  value={strategyText}
                  onChange={(e) => setStrategyText(e.target.value)}
                  placeholder="核心訊息、目標、語調…"
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
                {strategyError && (
                  <div style={{ fontSize: 11, color: c.vermillion }}>{strategyError}</div>
                )}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontSize: 12, color: c.inkMuted }}>欄位已育，可直接儲存。</span>
                  <Btn
                    t={t}
                    variant="seal"
                    size="sm"
                    onClick={savingStrategy ? undefined : handleSaveStrategy}
                    style={{ opacity: savingStrategy ? 0.5 : 1, cursor: savingStrategy ? "not-allowed" : "pointer" }}
                  >
                    {savingStrategy ? "儲存中…" : "儲存策略"}
                  </Btn>
                </div>
              </div>
            </details>
          </div>

          {/* Style manager */}
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
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 12,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: fontHead,
                    fontSize: 15,
                    fontWeight: 500,
                    color: c.ink,
                    letterSpacing: "0.04em",
                  }}
                >
                  文風管理
                </div>
                <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 4 }}>
                  三層 style 可直接 CRUD；預覽測試會直接本機 helper 產生測試文案。
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <Chip t={t} tone="muted">長期項目</Chip>
                <Btn
                  t={t}
                  variant="outline"
                  size="sm"
                  icon={ICONS.spark}
                  onClick={() =>
                    handleOpenFieldCopilot({
                      fieldId: "style",
                      fieldLabel: "文風設定",
                      currentPhase: "adapt",
                      suggestedSkill: "/marketing-adapt",
                      projectSummary: buildProjectSummary(project!),
                      conflictVersion: Object.keys(editingStyles)[0]
                        ? allStyles.find((style) => style.id === Object.keys(editingStyles)[0])?.updatedAt || null
                        : null,
                      conflictLabel: "文風",
                      fieldValue: Object.keys(editingStyles)[0]
                        ? {
                            title: editingStyles[Object.keys(editingStyles)[0]]?.title,
                            level: allStyles.find((style) => style.id === Object.keys(editingStyles)[0])?.level || "project",
                            platform: allStyles.find((style) => style.id === Object.keys(editingStyles)[0])?.platform,
                            content: editingStyles[Object.keys(editingStyles)[0]]?.content,
                          }
                        : allStyles.map((style) => ({
                            title: style.title,
                            level: style.level,
                            platform: style.platform,
                            content: style.content,
                          })),
                      relatedContext: "三層 style 組合：product + platform + project",
                      onApply: handleApplyStyle,
                    })
                  }
                >
                  帶進 AI —
                </Btn>
              </div>
            </div>

            {/* Existing styles list */}
            {allStyles.length === 0 ? (
              <div
                style={{
                  padding: "11px 14px",
                  background: c.paper,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: 2,
                  fontSize: 12.5,
                  color: c.inkMuted,
                  marginBottom: 10,
                }}
              >
                尚未設定文風 —
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
                {allStyles.map((s) => {
                  const editing = editingStyles[s.id];
                  const isSaving = savingStyleId === s.id;
                  return (
                    <div
                      key={s.id}
                      style={{
                        padding: "10px 14px",
                        background: c.paper,
                        border: `1px solid ${c.inkHair}`,
                        borderRadius: 2,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: editing ? 8 : 0,
                        }}
                      >
                        <div>
                          <span
                            style={{
                              fontFamily: fontBody,
                              fontSize: 13,
                              color: c.ink,
                              fontWeight: 500,
                            }}
                          >
                            {editing ? editing.title : s.title}
                          </span>
                          <span
                            style={{
                              fontFamily: fontMono,
                              fontSize: 10,
                              color: c.inkFaint,
                              marginLeft: 8,
                              letterSpacing: "0.08em",
                            }}
                          >
                            {s.level.toUpperCase()}
                          </span>
                        </div>
                        {!editing && (
                          <Btn
                            t={t}
                            variant="ghost"
                            size="sm"
                            onClick={() => startEditStyle(s)}
                          >
                            編輯
                          </Btn>
                        )}
                      </div>
                      {editing && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          <input
                            value={editing.title}
                            onChange={(e) =>
                              setEditingStyles((prev) => ({
                                ...prev,
                                [s.id]: { ...prev[s.id], title: e.target.value },
                              }))
                            }
                            style={{
                              padding: "6px 10px",
                              background: c.surface,
                              border: `1px solid ${c.inkHair}`,
                              borderRadius: 2,
                              fontFamily: fontBody,
                              fontSize: 12,
                              color: c.ink,
                              outline: "none",
                            }}
                          />
                          <textarea
                            value={editing.content}
                            onChange={(e) =>
                              setEditingStyles((prev) => ({
                                ...prev,
                                [s.id]: { ...prev[s.id], content: e.target.value },
                              }))
                            }
                            placeholder="文風描述…"
                            rows={3}
                            style={{
                              padding: "6px 10px",
                              background: c.surface,
                              border: `1px solid ${c.inkHair}`,
                              borderRadius: 2,
                              fontFamily: fontBody,
                              fontSize: 12,
                              color: c.ink,
                              outline: "none",
                              resize: "vertical",
                            }}
                          />
                          <div style={{ display: "flex", gap: 6 }}>
                            <Btn
                              t={t}
                              variant="seal"
                              size="sm"
                              onClick={isSaving ? undefined : () => handleSaveStyle(s.id)}
                              style={{ opacity: isSaving ? 0.5 : 1, cursor: isSaving ? "not-allowed" : "pointer" }}
                            >
                              {isSaving ? "儲存中…" : "儲存"}
                            </Btn>
                            <Btn
                              t={t}
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                setEditingStyles((prev) => {
                                  const next = { ...prev };
                                  delete next[s.id];
                                  return next;
                                })
                              }
                            >
                              取消
                            </Btn>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Add new style form */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 180px auto", gap: 8 }}>
              <input
                value={newStyleTitle}
                onChange={(e) => setNewStyleTitle(e.target.value)}
                placeholder="文風標題"
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
              <select
                value={newStyleLevel}
                onChange={(e) => setNewStyleLevel(e.target.value as "product" | "platform" | "project")}
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
                <option value="project">Project 級</option>
                <option value="platform">Platform 級</option>
                <option value="product">Product 級</option>
              </select>
              <Btn
                t={t}
                variant="ink"
                size="sm"
                icon={ICONS.plus}
                onClick={(addingStyle || !newStyleTitle.trim()) ? undefined : handleAddStyle}
                style={{ opacity: (addingStyle || !newStyleTitle.trim()) ? 0.5 : 1, cursor: (addingStyle || !newStyleTitle.trim()) ? "not-allowed" : "pointer" }}
              >
                {addingStyle ? "新增中…" : "新增"}
              </Btn>
            </div>
          </div>
        </div>

        <div
          style={{
            position: "sticky",
            top: 20,
            alignSelf: "flex-start",
          }}
        >
          <CoworkChatSheet
            campaignId={projectId}
            onError={(message) => setError(message)}
            open={copilotOpen}
            onOpenChange={setCopilotOpen}
            hideTrigger
            inlineOnly
            fieldContext={activeFieldContext}
            promptContext={activePromptContext}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Page entry ───────────────────────────────────────────────────────────────

export default function ZenInkMarketingWorkspace() {
  const { user } = useAuth();

  const [groups, setGroups] = useState<MarketingProjectGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const fetchGroups = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const data = await getMarketingProjectGroups(token);
      setGroups(data);
    } catch (err) {
      console.error("[ZenInkMarketing] fetch failed:", err);
      setError(err instanceof Error ? err.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void fetchGroups();
  }, [fetchGroups]);

  if (error && !openId) {
    return <InkErrorCard message={error} onRetry={fetchGroups} />;
  }

  if (openId) {
    return <InkMktDetail projectId={openId} onBack={() => setOpenId(null)} />;
  }

  const campaigns = flattenGroups(groups);

  return (
    <InkMktList
      campaigns={campaigns}
      loading={loading}
      onOpen={setOpenId}
      onNewCampaign={() => {
        /* P1 — create campaign flow */
      }}
    />
  );
}
