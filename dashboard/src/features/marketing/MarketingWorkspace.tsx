"use client";

import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import { GraphContextBadge } from "@/components/ai/GraphContextBadge";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { Badge, Button } from "@/components/zen/legacy";
import type { CopilotEntryConfig } from "@/lib/copilot/types";
import { REDACTION_RULES_VERSION } from "@/config/ai-redaction-rules";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/zen/legacy";
import { useAuth } from "@/lib/auth";
import { resolveCopilotWorkspaceId } from "@/lib/copilot/scope";
import {
  cancelCoworkRequest,
  CoworkCapabilityCheck,
  checkCoworkHelperHealth,
  CoworkStreamEvent,
  getDefaultHelperBaseUrl,
  getDefaultHelperCwd,
  getDefaultHelperModel,
  getDefaultHelperToken,
  setDefaultHelperBaseUrl,
  setDefaultHelperCwd,
  setDefaultHelperModel,
  setDefaultHelperToken,
  streamCoworkChat,
} from "@/lib/cowork-helper";
import { fetchGraphContext } from "@/lib/graph-context";
import {
  clearSessionStarted,
  markSessionStarted,
  readFreshSessionStartedAt,
} from "@/lib/copilot/session";
import {
  MarketingProject,
  MarketingProjectGroup,
  MarketingStyle,
  MarketingStyleBuckets,
  MarketingPrompt,
  Post,
  Strategy,
  WeekPlan,
  getMarketingPrompts,
  publishMarketingPrompt,
  updateMarketingPromptDraft,
} from "@/lib/marketing-api";
import {
  buildMarketingKnowledgePrompt,
  COWORK_MAX_TURNS,
  graphContextUnavailableNotice,
  MARKETING_STRATEGY_TARGET_FIELDS,
  normalizeSourceCitations,
} from "@/lib/cowork-knowledge";
import type { GraphContextResponse } from "@/lib/api";
import {
  buildContextPack,
  buildDiscussionPrompt,
  buildPromptDraftDiscussionPrompt,
  buildProjectSummary,
  campaignStatusConfig,
  ChatStatus,
  composeStyleMarkdown,
  deriveProjectStage,
  DiscussionFieldId,
  DiscussionPhase,
  FieldDiscussionConfig,
  formatContentMix,
  formatCsv,
  isConfirmedStatus,
  isPlannedStatus,
  nextChatStatus,
  parseContentMix,
  parseCoworkStreamLine,
  parseCsv,
  parseStructuredApplyPayload,
  postNextStepHint,
  PromptDraftDiscussionConfig,
  primaryCtaForProject,
  requiresReview,
  statusConfig,
  stylePreviewPrompt,
  StructuredApplyPayload,
} from "@/features/marketing/logic";
import { useMarketingWorkspace } from "@/features/marketing/useMarketingWorkspace";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  BookCopy,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  Clock3,
  Copy,
  Eye,
  Heart,
  ImageIcon,
  MessageCircle,
  Monitor,
  Pencil,
  PlugZap,
  RefreshCw,
  Repeat2,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

type Campaign = MarketingProject;
type CampaignGroup = MarketingProjectGroup;

const platformIcon: Record<string, string> = {
  Threads: "T",
  IG: "IG",
  Blog: "B",
  FB: "FB",
};

const platformColor: Record<string, string> = {
  Threads: "bg-foreground/10 text-foreground",
  IG: "bg-pink-500/10 text-pink-400",
  Blog: "bg-chart-2/10 text-chart-2",
  FB: "bg-blue-500/10 text-blue-400",
};

function MetricPill({ icon: Icon, value }: { icon: typeof Heart; value: number | undefined }) {
  if (!value) return null;
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Icon className="h-3 w-3" />
      {value}
    </span>
  );
}

function CopilotLaunchButton({
  onClick,
  children = "帶進 AI",
  className = "",
}: {
  onClick: () => void;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <Button size="sm" variant="outline" className={`h-7 gap-1.5 rounded-full px-3 text-[11px] ${className}`.trim()} onClick={onClick}>
      <PlugZap className="h-3.5 w-3.5" />
      {children}
    </Button>
  );
}

function getStrategySaveBlockers(input: {
  projectType: Campaign["projectType"];
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

export function CampaignList({ groups, onSelect }: { groups: CampaignGroup[]; onSelect: (id: string) => void }) {
  const totalReview = groups.reduce(
    (n, group) =>
      n + group.projects.reduce((acc, project) => acc + project.posts.filter((p) => requiresReview(p.status)).length, 0),
    0
  );

  if (groups.length === 0) {
    return (
      <div className="rounded-xl border border-border/40 bg-card/50 p-6 text-sm text-muted-foreground">
        目前沒有可顯示的行銷項目。
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {totalReview > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-400/20 bg-amber-400/5 px-4 py-2.5">
          <Eye className="h-4 w-4 text-amber-400" />
          <span className="text-sm text-foreground">
            <strong className="text-amber-400">{totalReview} 篇貼文</strong>等你確認
          </span>
        </div>
      )}

      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.product.id || group.product.name} className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[0.65rem] tracking-[0.01em]">
                {group.product.name}
              </Badge>
              <span className="text-[11px] font-medium text-[#c5d8ea]">{group.projects.length} 個項目</span>
            </div>
            <div className="space-y-3">
              {group.projects.map((campaign) => {
                const sc = campaignStatusConfig(campaign.status);
                const reviewCount = campaign.posts.filter((p) => requiresReview(p.status)).length;
                return (
                  <div
                    key={campaign.id}
                    className="group cursor-pointer rounded-xl border border-border/60 bg-card/80 shadow-[0_14px_34px_rgba(0,0,0,0.18)] transition-all hover:border-primary/20 hover:bg-card hover:shadow-[0_18px_40px_rgba(0,0,0,0.24)]"
                    onClick={() => onSelect(campaign.id)}
                  >
                    <div className="space-y-3 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <div className={`h-2 w-2 rounded-full ${sc.dot}`} />
                            <span className="font-medium text-foreground">{campaign.name}</span>
                            <Badge variant="outline" className={`text-[0.6rem] ${sc.badge}`}>
                              {sc.label}
                            </Badge>
                            <Badge variant="outline" className="text-[0.55rem]">
                              {campaign.projectType === "long_term" ? "長期經營" : "短期活動"}
                            </Badge>
                          </div>
                          <p className="ml-4 mt-1 text-xs leading-5 text-[#c4d8e9]">{campaign.description}</p>
                        </div>
                        {reviewCount > 0 && (
                          <Badge className="shrink-0 border-amber-400/30 bg-amber-400/10 text-[0.6rem] text-amber-400">
                            {reviewCount} 待確認
                          </Badge>
                        )}
                      </div>

                      {campaign.blockReason ? (
                        <div className="ml-4 flex items-start gap-2 text-xs text-destructive/80">
                          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          <span>{campaign.blockReason}</span>
                        </div>
                      ) : (
                        <div className="ml-4 flex items-center gap-6">
                          <div>
                            <div className="text-sm font-semibold text-foreground">{campaign.stats.followers}</div>
                            <div className="text-[0.55rem] font-medium uppercase tracking-[0.08em] text-[#abc3d8]">追蹤者</div>
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-foreground">{campaign.stats.avgEngagement}</div>
                            <div className="text-[0.55rem] font-medium uppercase tracking-[0.08em] text-[#abc3d8]">平均互動率</div>
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-foreground">{campaign.stats.postsThisMonth}</div>
                            <div className="text-[0.55rem] font-medium uppercase tracking-[0.08em] text-[#abc3d8]">本月發文</div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CampaignStarter({
  productOptions,
  onCreateCampaign,
  creatingCampaign,
}: {
  productOptions: Array<{ id: string | null; name: string }>;
  onCreateCampaign: (input: {
    productId: string;
    name: string;
    description: string;
    projectType: "long_term" | "short_term";
    dateRange?: { start: string; end: string } | null;
  }) => Promise<void>;
  creatingCampaign: boolean;
}) {
  const [productId, setProductId] = useState(productOptions[0]?.id || "");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [projectType, setProjectType] = useState<"long_term" | "short_term">("long_term");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const canSubmit =
    name.trim().length >= 2 &&
    productId.trim().length >= 1 &&
    !creatingCampaign &&
    (projectType === "long_term" || (dateStart && dateEnd));

  return (
    <div className="rounded-xl border border-border/60 bg-card/80 p-4 shadow-[0_16px_36px_rgba(0,0,0,0.18)]">
      <div className="mb-3">
        <h3 className="text-sm font-medium text-foreground">建立行銷項目</h3>
        <p className="mt-1 text-xs text-muted-foreground">先選產品，再建立長期經營或短期活動項目。</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {productOptions.length > 0 ? (
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="h-9 rounded-md border border-border/50 bg-background px-2 text-sm text-foreground outline-none ring-0 focus:border-primary/50"
          >
            {productOptions.map((product) => (
              <option key={product.id || product.name} value={product.id || ""}>
                {product.name}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            placeholder="產品 ID（目前尚未載入產品清單）"
            className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
          />
        )}
        <select
          value={projectType}
          onChange={(e) => setProjectType(e.target.value as "long_term" | "short_term")}
          className="h-9 rounded-md border border-border/50 bg-background px-2 text-sm text-foreground outline-none ring-0 focus:border-primary/50"
        >
          <option value="long_term">長期經營</option>
          <option value="short_term">短期活動</option>
        </select>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="項目名稱（例如：官網 Blog）"
          className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
        />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="活動描述（選填）"
          className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
        />
        {projectType === "short_term" && (
          <>
            <input
              type="date"
              value={dateStart}
              onChange={(e) => setDateStart(e.target.value)}
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 focus:border-primary/50"
            />
            <input
              type="date"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 focus:border-primary/50"
            />
          </>
        )}
      </div>
      <div className="mt-2 flex justify-end">
        <Button
          size="sm"
          className="h-9"
          disabled={!canSubmit}
          onClick={async () => {
            if (!canSubmit) return;
            await onCreateCampaign({
              productId: productId.trim(),
              name: name.trim(),
              description: description.trim(),
              projectType,
              dateRange: projectType === "short_term" ? { start: dateStart, end: dateEnd } : null,
            });
            setName("");
            setDescription("");
            setDateStart("");
            setDateEnd("");
          }}
        >
          建立項目
        </Button>
      </div>
    </div>
  );
}

export function StrategyAndPlan({
  campaign,
  strategy,
  contentPlan,
  posts = [],
  onSavePlan,
  savingPlan = false,
  onError,
  onOpenCopilot,
}: {
  campaign: Campaign;
  strategy: Strategy;
  contentPlan?: WeekPlan[];
  posts?: Post[];
  onSavePlan?: (contentPlan: WeekPlan[]) => Promise<void>;
  savingPlan?: boolean;
  onError: (message: string) => void;
  onOpenCopilot?: (config: FieldDiscussionConfig) => void;
}) {
  const [showStrategy, setShowStrategy] = useState(false);
  const [editingPlan, setEditingPlan] = useState(false);
  const [draftPlan, setDraftPlan] = useState<WeekPlan[]>(contentPlan || []);

  useEffect(() => {
    setDraftPlan(contentPlan || []);
  }, [contentPlan]);

  const planStatusDot = {
    published: "bg-muted-foreground/40",
    confirmed: "bg-primary",
    suggested: "bg-amber-400",
  } as const;

  const planRows = editingPlan ? draftPlan : contentPlan || [];

  const updateDayField = (weekIndex: number, dayIndex: number, field: "day" | "platform" | "topic", value: string) => {
    setDraftPlan((prev) =>
      prev.map((week, wi) =>
        wi !== weekIndex
          ? week
          : {
              ...week,
              days: week.days.map((day, di) => (di !== dayIndex ? day : { ...day, [field]: value })),
            }
      )
    );
  };

  const removeDay = (weekIndex: number, dayIndex: number) => {
    const target = draftPlan[weekIndex]?.days?.[dayIndex];
    if (!target) return;
    const linkedPost = posts.find((post) => post.title === target.topic);
    if (linkedPost && !["topic_planned", "published", "failed"].includes(linkedPost.status)) {
      window.alert("這個主題已進入內容生成流程，不能直接刪除；請先處理進行中的貼文。");
      return;
    }
    setDraftPlan((prev) =>
      prev.map((week, wi) =>
        wi !== weekIndex
          ? week
          : {
              ...week,
              days: week.days.filter((_, di) => di !== dayIndex),
            }
      )
    );
  };

  const addDay = (weekIndex: number) => {
    setDraftPlan((prev) =>
      prev.map((week, wi) =>
        wi !== weekIndex
          ? week
          : {
              ...week,
              days: [...week.days, { day: "Fri", platform: "Threads", topic: "新增主題", status: "suggested" }],
            }
      )
    );
  };

  const scheduleRows = (contentPlan || []).flatMap((week) =>
    week.days.map((day) => ({
      date: day.day,
      platform: day.platform,
      topic: day.topic,
      reason: week.aiNote || "",
    }))
  );

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-border/40 bg-card/60">
        <button
          className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/10"
          onClick={() => setShowStrategy(!showStrategy)}
        >
          <Target className="h-4 w-4 shrink-0 text-primary" />
          <span className="flex-1 text-sm font-medium text-foreground">發文策略</span>
          <span className="mr-1 text-xs text-muted-foreground">{strategy.frequency}</span>
          {showStrategy ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </button>
        {showStrategy && (
          <div className="grid gap-2 border-t border-border/30 px-4 py-3 sm:grid-cols-2">
            <div>
              <div className="text-[0.6rem] text-muted-foreground">目標受眾</div>
              <div className="mt-0.5 text-xs text-foreground">{formatCsv(strategy.audience)}</div>
            </div>
            <div>
              <div className="text-[0.6rem] text-muted-foreground">語氣風格</div>
              <div className="mt-0.5 text-xs text-foreground">{strategy.tone}</div>
            </div>
            <div>
              <div className="text-[0.6rem] text-muted-foreground">核心訊息</div>
              <div className="mt-0.5 text-xs text-foreground">{strategy.coreMessage}</div>
            </div>
            <div>
              <div className="text-[0.6rem] text-muted-foreground">發文平台</div>
              <div className="mt-0.5 text-xs text-foreground">{formatCsv(strategy.platforms)}</div>
            </div>
            {strategy.frequency && (
              <div>
                <div className="text-[0.6rem] text-muted-foreground">發文頻率</div>
                <div className="mt-0.5 text-xs text-foreground">{strategy.frequency}</div>
              </div>
            )}
            {Object.keys(strategy.contentMix || {}).length > 0 && (
              <div>
                <div className="text-[0.6rem] text-muted-foreground">內容比例</div>
                <div className="mt-0.5 text-xs text-foreground">{formatContentMix(strategy.contentMix)}</div>
              </div>
            )}
            {strategy.campaignGoal && (
              <div>
                <div className="text-[0.6rem] text-muted-foreground">活動目標</div>
                <div className="mt-0.5 text-xs text-foreground">{strategy.campaignGoal}</div>
              </div>
            )}
            {strategy.ctaStrategy && (
              <div>
                <div className="text-[0.6rem] text-muted-foreground">CTA 策略</div>
                <div className="mt-0.5 text-xs text-foreground">{strategy.ctaStrategy}</div>
              </div>
            )}
            {strategy.referenceMaterials.length > 0 && (
              <div className="sm:col-span-2">
                <div className="text-[0.6rem] text-muted-foreground">參考素材</div>
                <div className="mt-0.5 text-xs text-foreground">{formatCsv(strategy.referenceMaterials)}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {contentPlan && contentPlan.length > 0 && (
        <div className="rounded-xl border border-border/40 bg-card/60">
          <div className="flex items-center justify-between gap-3 border-b border-border/30 px-4 py-3">
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 shrink-0 text-primary" />
              <span className="text-sm font-medium text-foreground">內容排程</span>
            </div>
            {onSavePlan && (
              <div className="flex items-center gap-2">
                <CopilotLaunchButton
                  onClick={() =>
                    onOpenCopilot?.({
                      fieldId: "schedule",
                      fieldLabel: "排程設定",
                      currentPhase: "schedule",
                      suggestedSkill: "/marketing-plan",
                      projectSummary: buildProjectSummary(campaign),
                      fieldValue: scheduleRows,
                      relatedContext: strategy.summaryEntry || strategy.coreMessage,
                      onApply: async (payload) => {
                        if (payload.targetField !== "schedule" || !Array.isArray(payload.value)) {
                          throw new Error("AI 輸出的排程格式不正確");
                        }
                        const nextPlan: WeekPlan[] = [
                          {
                            weekLabel: "AI 建議排程",
                            isCurrent: true,
                            days: payload.value.map((item) => {
                              const row = item as Record<string, unknown>;
                              return {
                                day: String(row.date || row.day || "").trim() || "待定",
                                platform: String(row.platform || "Threads").trim(),
                                topic: String(row.topic || "").trim(),
                                status: "suggested" as const,
                              };
                            }),
                            aiNote: payload.value
                              .map((item) => String((item as Record<string, unknown>).reason || "").trim())
                              .filter(Boolean)
                              .join(" / "),
                          },
                        ];
                        setDraftPlan(nextPlan);
                        await onSavePlan(nextPlan);
                      },
                    })
                  }
                >
                  帶進 AI
                </CopilotLaunchButton>
                {editingPlan && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-[11px]"
                    onClick={() => {
                      setDraftPlan(contentPlan || []);
                      setEditingPlan(false);
                    }}
                  >
                    取消
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  onClick={async () => {
                    if (!editingPlan) {
                      setEditingPlan(true);
                      return;
                    }
                    await onSavePlan(draftPlan);
                    setEditingPlan(false);
                  }}
                >
                  {editingPlan ? (savingPlan ? "儲存中..." : "儲存排程") : "調整排程"}
                </Button>
              </div>
            )}
          </div>
          <div className="divide-y divide-border/20">
            {planRows.map((week, weekIndex) => (
              <div key={week.weekLabel} className="px-4 py-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className={`text-xs font-medium ${week.isCurrent ? "text-foreground" : "text-muted-foreground"}`}>{week.weekLabel}</span>
                </div>
                <div className="space-y-1.5">
                  {week.days.map((day, i) =>
                    editingPlan ? (
                      <div key={`${day.day}-${day.platform}-${i}`} className="grid gap-2 rounded-md border border-border/20 bg-background/50 p-2 text-xs sm:grid-cols-[64px_100px_1fr_72px]">
                        <input
                          value={day.day}
                          onChange={(e) => updateDayField(weekIndex, i, "day", e.target.value)}
                          className="h-8 rounded-md border border-border/50 bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50"
                        />
                        <input
                          value={day.platform}
                          onChange={(e) => updateDayField(weekIndex, i, "platform", e.target.value)}
                          className="h-8 rounded-md border border-border/50 bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50"
                        />
                        <input
                          value={day.topic}
                          onChange={(e) => updateDayField(weekIndex, i, "topic", e.target.value)}
                          className="h-8 rounded-md border border-border/50 bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50"
                        />
                        <Button size="sm" variant="outline" className="h-8 text-[11px]" onClick={() => removeDay(weekIndex, i)}>
                          刪除
                        </Button>
                      </div>
                    ) : (
                      <div key={`${day.day}-${day.platform}-${i}`} className="flex items-center gap-3 text-xs">
                        <span className="w-8 shrink-0 text-muted-foreground">{day.day}</span>
                        <span className={`w-7 shrink-0 rounded px-1 py-0.5 text-center text-[0.55rem] font-medium ${platformColor[day.platform] || "bg-muted/20 text-muted-foreground"}`}>
                          {platformIcon[day.platform] || day.platform}
                        </span>
                        <span className="flex-1 text-foreground/85">{day.topic}</span>
                        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${planStatusDot[day.status]}`} />
                      </div>
                    )
                  )}
                </div>
                {editingPlan && (
                  <div className="mt-2">
                    <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => addDay(weekIndex)}>
                      新增一筆
                    </Button>
                  </div>
                )}
                {week.aiNote && (
                  <div className="mt-2 flex items-start gap-1.5 text-[0.6rem] text-muted-foreground">
                    <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
                    <span>{week.aiNote}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PostCard({
  campaignId,
  post,
  onReview,
  isReviewing,
  onError,
  onOpenCopilot,
}: {
  campaignId: string;
  post: Post;
  onReview: (postId: string, action: "approve" | "request_changes" | "reject") => void;
  isReviewing: boolean;
  onError: (message: string) => void;
  onOpenCopilot?: (config: FieldDiscussionConfig) => void;
}) {
  const [open, setOpen] = useState(false);
  const [copiedAction, setCopiedAction] = useState<"" | "adapt" | "publish">("");
  const sc = statusConfig(post.status);
  const isReview = requiresReview(post.status);
  const isPlanned = isPlannedStatus(post.status);
  const isConfirmed = isConfirmedStatus(post.status);
  const isMasterConfirmed = post.status === "draft_confirmed";
  const isPlatformConfirmed = post.status === "platform_confirmed";

  return (
    <div className={`rounded-xl border ${isReview ? "border-l-4 border-l-amber-400 border-amber-400/25" : "border-border/40"} bg-card/70`}>
      <div className="flex cursor-pointer items-center gap-3 p-3" onClick={() => setOpen(!open)}>
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${platformColor[post.platform] || "bg-muted/20 text-muted-foreground"}`}>
          {platformIcon[post.platform] || post.platform}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">{post.title}</div>
          <div className="text-xs text-muted-foreground">{post.publishedAt || post.scheduledAt || ""}</div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {post.metrics && (
            <div className="hidden items-center gap-2 sm:flex">
              <MetricPill icon={Heart} value={post.metrics.likes} />
              <MetricPill icon={MessageCircle} value={post.metrics.comments} />
              <MetricPill icon={Repeat2} value={post.metrics.shares} />
            </div>
          )}
          <Badge variant="outline" className={`text-[0.55rem] ${sc.class}`}>{sc.label}</Badge>
          {open ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
        </div>
      </div>

      {open && (
        <div className="space-y-4 border-t border-border/30 p-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
            <div className="rounded-lg border border-border/30 bg-background/60 p-4">
              <div className="whitespace-pre-line text-sm leading-relaxed text-foreground/90">{post.preview}</div>
            </div>
            {post.imageDesc && (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/40 bg-muted/10 p-3 text-center">
                <ImageIcon className="mb-2 h-6 w-6 text-muted-foreground/30" />
                <p className="text-[0.6rem] leading-relaxed text-muted-foreground">{post.imageDesc}</p>
              </div>
            )}
          </div>

          {post.aiReason && (
            <div className="flex items-start gap-2 rounded-md border border-primary/10 bg-primary/5 px-3 py-2 text-xs">
              <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <span className="text-foreground/80">{post.aiReason}</span>
            </div>
          )}

          {isReview && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <CopilotLaunchButton
                  onClick={() =>
                    onOpenCopilot?.({
                      fieldId: "review",
                      fieldLabel: "審核建議",
                      currentPhase: post.status === "platform_adapted" ? "adapt" : "generate",
                      suggestedSkill: post.status === "platform_adapted" ? "/marketing-adapt" : "/marketing-generate",
                      projectSummary: `${campaignId} / ${post.platform} / ${post.title}`,
                      fieldValue: {
                        title: post.title,
                        preview: post.preview,
                        platform: post.platform,
                        ai_reason: post.aiReason || "",
                      },
                      relatedContext: "請幫我判斷這版文案該直接核准、要求修改，或退回重做，並說明理由。",
                    })
                  }
                >
                  帶進 AI
                </CopilotLaunchButton>
                <div className="text-xs text-muted-foreground">可以先跟 AI 討論，再決定核准或退回。</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  disabled={isReviewing}
                  className="h-8 gap-1.5 border border-primary/30 bg-primary/10 text-xs text-primary hover:bg-primary/20"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReview(post.id, "approve");
                  }}
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />核准文案
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isReviewing}
                  className="h-8 gap-1.5 text-xs text-muted-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReview(post.id, "request_changes");
                  }}
                >
                  <Pencil className="h-3.5 w-3.5" />要求修改
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isReviewing}
                  className="h-8 gap-1.5 text-xs text-destructive/70"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReview(post.id, "reject");
                  }}
                >
                  <RefreshCw className="h-3.5 w-3.5" />退回重做
                </Button>
              </div>
            </div>
          )}

          {isPlanned && postNextStepHint(post) && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Zap className="h-3.5 w-3.5 text-primary" />
              {postNextStepHint(post)}
            </div>
          )}

          {isConfirmed && postNextStepHint(post) && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Zap className="h-3.5 w-3.5 text-primary" />
                {postNextStepHint(post)}
              </div>
              <div className="flex flex-wrap gap-2">
                {isMasterConfirmed && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 gap-1.5 text-[11px]"
                    onClick={async (e) => {
                      e.stopPropagation();
                      const cmd = `/marketing-adapt master_post_id=${post.id} platforms=Threads,IG,FB`;
                      await navigator.clipboard.writeText(cmd);
                      setCopiedAction("adapt");
                      setTimeout(() => setCopiedAction(""), 1200);
                    }}
                  >
                    <Copy className="h-3 w-3" />
                    {copiedAction === "adapt" ? "已複製適配指令" : "複製適配指令"}
                  </Button>
                )}
                {isPlatformConfirmed && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 gap-1.5 text-[11px]"
                    onClick={async (e) => {
                      e.stopPropagation();
                      const cmd = `/marketing-publish post_id=${post.id} schedule_at=<ISO時間> channel_account_id=<Postiz帳號ID> dry_run=false`;
                      await navigator.clipboard.writeText(cmd);
                      setCopiedAction("publish");
                      setTimeout(() => setCopiedAction(""), 1200);
                    }}
                  >
                    <Copy className="h-3 w-3" />
                    {copiedAction === "publish" ? "已複製發佈指令" : "複製發佈指令"}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CommandRow({
  title,
  command,
}: {
  title: string;
  command: string;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="rounded-md border border-border/40 bg-background/70 p-2.5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium text-foreground">{title}</span>
        <Button
          size="sm"
          variant="outline"
          className="h-6 px-2 text-[10px]"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(command);
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            } catch {
              setCopied(false);
            }
          }}
        >
          <Copy className="mr-1 h-3 w-3" />
          {copied ? "已複製" : "複製"}
        </Button>
      </div>
      <code className="block overflow-x-auto whitespace-nowrap text-[11px] text-muted-foreground">{command}</code>
    </div>
  );
}

export function FlowGuideSheet({ campaignId }: { campaignId: string | null }) {
  const cid = campaignId || "<project_id>";
  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs">
            <CircleHelp className="h-3.5 w-3.5" />
            流程指引
          </Button>
        }
      />
      <SheetContent side="right" className="overflow-y-auto p-0 sm:max-w-md">
        <SheetHeader className="border-b border-border/40">
          <SheetTitle>怎麼操作（簡單版）</SheetTitle>
          <SheetDescription>你只要照下面 4 步做就可以。</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 p-4 text-xs">
          <section className="space-y-2 rounded-lg border border-border/40 bg-card/70 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Monitor className="h-4 w-4 text-primary" />
              第 1 步（在這頁）
            </div>
            <div className="space-y-1 text-muted-foreground">
              <p>1. 選一個活動</p>
              <p>2. 按「建立主題」</p>
              <p>3. 等文案回來後，在這頁按「核准文案 / 要求修改」</p>
            </div>
          </section>

          <section className="space-y-2 rounded-lg border border-border/40 bg-card/70 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Bot className="h-4 w-4 text-primary" />
              第 2 步（用 Claude 產內容）
            </div>
            <div className="space-y-2">
              <div className="text-[11px] text-muted-foreground">
                可直接在「建立行銷寫作計畫」右上角按 <strong>AI 討論（Beta）</strong>，或用下列指令在 cowork 執行。
              </div>
              <CommandRow
                title="先產生文案"
                command={`/marketing-generate project_id=${cid} topic="你的主題" platform_hint=Threads`}
              />
              <CommandRow
                title="核准後做多平台"
                command={`在貼文卡片按「複製適配指令」，貼到 Claude 直接送出`}
              />
              <CommandRow
                title="最後送發文"
                command={`在貼文卡片按「複製發佈指令」，再補 schedule_at / channel_account_id`}
              />
            </div>
          </section>

          <section className="space-y-2 rounded-lg border border-border/40 bg-card/70 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Clock3 className="h-4 w-4 text-primary" />
              Runner 是什麼？
            </div>
            <p className="text-muted-foreground">
              它是自動排程機器。你現在可以先忽略，先用上面 2 步把流程跑起來。
            </p>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export function PromptManagerSheet({
  user,
  onError,
  onOpenPromptCopilot,
}: {
  user: { getIdToken: () => Promise<string> } | null;
  onError: (message: string) => void;
  onOpenPromptCopilot: (config: PromptDraftDiscussionConfig) => void;
}) {
  const [prompts, setPrompts] = useState<MarketingPrompt[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string>("marketing-generate");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [open, setOpen] = useState(false);

  const loadPrompts = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const token = await user.getIdToken();
      const res = await getMarketingPrompts(token);
      setPrompts(res.prompts);
      const nextDrafts: Record<string, string> = {};
      for (const prompt of res.prompts) {
        nextDrafts[prompt.skill] = prompt.draftContent || "";
      }
      setDrafts(nextDrafts);
      if (!res.prompts.find((p) => p.skill === selectedSkill) && res.prompts.length > 0) {
        setSelectedSkill(res.prompts[0].skill);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "載入 prompt 失敗");
    } finally {
      setLoading(false);
    }
  }, [user, selectedSkill, onError]);

  const activePrompt = useMemo(
    () => prompts.find((p) => p.skill === selectedSkill) || prompts[0] || null,
    [prompts, selectedSkill]
  );

  useEffect(() => {
    if (!user) return;
    loadPrompts().catch(() => undefined);
  }, [user, loadPrompts]);

  const handleSaveDraft = useCallback(async () => {
    if (!user || !activePrompt) return;
    const content = (drafts[activePrompt.skill] || "").trim();
    if (content.length < 10) {
      onError("Prompt 太短，至少 10 個字");
      return;
    }
    setSaving(true);
    try {
      const token = await user.getIdToken();
      const updated = await updateMarketingPromptDraft(token, activePrompt.skill, content);
      setPrompts((prev) => prev.map((p) => (p.skill === updated.skill ? updated : p)));
      setDrafts((prev) => ({ ...prev, [updated.skill]: updated.draftContent }));
    } catch (err) {
      onError(err instanceof Error ? err.message : "儲存 draft 失敗");
    } finally {
      setSaving(false);
    }
  }, [user, activePrompt, drafts, onError]);

  const handlePublish = useCallback(
    async (sourceVersion?: number) => {
      if (!user || !activePrompt) return;
      setPublishing(true);
      try {
        const token = await user.getIdToken();
        const updated = await publishMarketingPrompt(token, activePrompt.skill, sourceVersion ? { sourceVersion } : {});
        setPrompts((prev) => prev.map((p) => (p.skill === updated.skill ? updated : p)));
        setDrafts((prev) => ({ ...prev, [updated.skill]: updated.draftContent }));
      } catch (err) {
        onError(err instanceof Error ? err.message : "發布 prompt 失敗");
      } finally {
        setPublishing(false);
      }
    },
    [user, activePrompt, onError]
  );

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs">
            <BookCopy className="h-3.5 w-3.5" />
            Prompt SSOT
          </Button>
        }
      />
      <SheetContent side="right" className="overflow-y-auto p-0 sm:max-w-2xl">
        <SheetHeader className="border-b border-border/40">
          <SheetTitle>行銷 Prompt SSOT</SheetTitle>
          <SheetDescription>全公司共用，同一份發布版本。</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 p-4">
          {loading ? (
          <div className="rounded-lg border border-border/60 bg-card/80 p-3 text-xs text-muted-foreground">載入中...</div>
          ) : activePrompt ? (
            <>
              <div className="flex flex-wrap gap-2">
                {prompts.map((prompt) => (
                  <Button
                    key={prompt.skill}
                    size="sm"
                    variant={prompt.skill === activePrompt.skill ? "default" : "outline"}
                    className="h-7 text-[11px]"
                    onClick={() => setSelectedSkill(prompt.skill)}
                  >
                    {prompt.title}
                  </Button>
                ))}
              </div>

              <div className="rounded-lg border border-border/40 bg-card/60 p-3">
                <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                  <span className="font-medium text-foreground">
                    {activePrompt.title} Draft
                  </span>
                  <span className="text-muted-foreground">
                    Published v{activePrompt.publishedVersion}
                  </span>
                </div>
                <textarea
                  value={drafts[activePrompt.skill] || ""}
                  onChange={(e) =>
                    setDrafts((prev) => ({ ...prev, [activePrompt.skill]: e.target.value }))
                  }
                  className="min-h-[220px] w-full rounded-md border border-border/50 bg-background px-3 py-2 text-xs leading-relaxed text-foreground outline-none ring-0 focus:border-primary/50"
                />
                <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={saving || publishing}
                    onClick={() => {
                      onOpenPromptCopilot({
                        skill: activePrompt.skill,
                        title: activePrompt.title,
                        projectSummary: "行銷 Prompt SSOT",
                        draftContent: drafts[activePrompt.skill] || "",
                        publishedContent: activePrompt.publishedContent,
                        publishedVersion: activePrompt.publishedVersion,
                        draftUpdatedAt: activePrompt.draftUpdatedAt,
                        onApply: async (payload) => {
                          if (payload.targetField !== "marketing_prompt_draft" || !payload.value || typeof payload.value !== "object") {
                            throw new Error("AI 輸出的 prompt draft 結構不正確");
                          }
                          const nextContent = String((payload.value as Record<string, unknown>).content || "").trim();
                          if (nextContent.length < 10) {
                            throw new Error("AI 輸出的 prompt draft 太短");
                          }
                          const token = await user?.getIdToken();
                          if (!token) {
                            throw new Error("尚未登入，無法更新 prompt draft");
                          }
                          const updated = await updateMarketingPromptDraft(token, activePrompt.skill, nextContent);
                          setPrompts((prev) => prev.map((p) => (p.skill === updated.skill ? updated : p)));
                          setDrafts((prev) => ({ ...prev, [updated.skill]: updated.draftContent }));
                        },
                      });
                      setOpen(false);
                    }}
                  >
                    用 AI 討論 Draft
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={saving || publishing}
                    onClick={handleSaveDraft}
                  >
                    {saving ? "儲存中..." : "儲存 Draft"}
                  </Button>
                  <Button
                    size="sm"
                    disabled={saving || publishing}
                    onClick={() => handlePublish()}
                  >
                    {publishing ? "發布中..." : "發布為最新版本"}
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-border/40 bg-card/60 p-3">
                <div className="mb-2 text-xs font-medium text-foreground">版本紀錄</div>
                <div className="space-y-2">
                  {activePrompt.history.map((item) => (
                    <div
                      key={`${activePrompt.skill}-${item.version}`}
                      className="flex items-center justify-between rounded-md border border-border/40 bg-background/70 px-2.5 py-2"
                    >
                      <div className="min-w-0">
                        <div className="text-[11px] text-foreground">
                          v{item.version} {item.isPublished ? "（目前）" : ""}
                        </div>
                        <div className="truncate text-[10px] text-muted-foreground">
                          {item.createdAt} · {item.createdBy || "unknown"} · {item.note || "—"}
                        </div>
                      </div>
                      {!item.isPublished && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 px-2 text-[10px]"
                          disabled={publishing}
                          onClick={() => handlePublish(item.version)}
                        >
                          回滾為此版
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-border/40 bg-card/60 p-3 text-xs text-muted-foreground">
              沒有可用的 prompt。
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function previewText(value: unknown): string {
  if (value == null) return "尚未設定";
  if (typeof value === "string") return value.trim() || "尚未設定";
  if (Array.isArray(value)) {
    return value.length === 0 ? "尚未設定" : value.map((item) => previewText(item)).join("\n");
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function fieldValueFromRecord(record: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (key in record) return record[key];
  }
  return undefined;
}

function buildApplyChangePreview(
  field: FieldDiscussionConfig | undefined,
  promptContext: PromptDraftDiscussionConfig | undefined,
  payload: StructuredApplyPayload | null
): Array<{ label: string; before: string; after: string }> {
  if (!payload) return [];
  if (payload.targetField === "marketing_prompt_draft" && promptContext) {
    const nextRecord = typeof payload.value === "object" && payload.value ? (payload.value as Record<string, unknown>) : {};
    return [
      {
        label: `${promptContext.title} Draft`,
        before: previewText(promptContext.draftContent),
        after: previewText(fieldValueFromRecord(nextRecord, "content")),
      },
    ].filter((item) => item.before !== item.after);
  }
  if (!field) return [];
  const current = field.fieldValue;
  const next = payload.value;

  if (payload.targetField === "strategy" && typeof current === "object" && current && typeof next === "object" && next) {
    const currentRecord = current as Record<string, unknown>;
    const nextRecord = next as Record<string, unknown>;
    const items = [
      { label: "目標受眾", before: previewText(fieldValueFromRecord(currentRecord, "audience")), after: previewText(fieldValueFromRecord(nextRecord, "audience")) },
      { label: "語氣", before: previewText(fieldValueFromRecord(currentRecord, "tone")), after: previewText(fieldValueFromRecord(nextRecord, "tone")) },
      { label: "核心訊息", before: previewText(fieldValueFromRecord(currentRecord, "core_message", "coreMessage")), after: previewText(fieldValueFromRecord(nextRecord, "core_message", "coreMessage")) },
      { label: "平台", before: previewText(fieldValueFromRecord(currentRecord, "platforms")), after: previewText(fieldValueFromRecord(nextRecord, "platforms")) },
      { label: "發文頻率", before: previewText(fieldValueFromRecord(currentRecord, "frequency")), after: previewText(fieldValueFromRecord(nextRecord, "frequency")) },
      { label: "內容比例", before: previewText(fieldValueFromRecord(currentRecord, "content_mix", "contentMix")), after: previewText(fieldValueFromRecord(nextRecord, "content_mix", "contentMix")) },
      { label: "活動目標", before: previewText(fieldValueFromRecord(currentRecord, "campaign_goal", "campaignGoal")), after: previewText(fieldValueFromRecord(nextRecord, "campaign_goal", "campaignGoal")) },
      { label: "CTA 策略", before: previewText(fieldValueFromRecord(currentRecord, "cta_strategy", "ctaStrategy")), after: previewText(fieldValueFromRecord(nextRecord, "cta_strategy", "ctaStrategy")) },
    ];
    return items.filter((item) => item.before !== item.after);
  }

  if (payload.targetField === "topic" && typeof current === "object" && current && typeof next === "object" && next) {
    const currentRecord = current as Record<string, unknown>;
    const nextRecord = next as Record<string, unknown>;
    const items = [
      { label: "主題名稱", before: previewText(fieldValueFromRecord(currentRecord, "title")), after: previewText(fieldValueFromRecord(nextRecord, "title")) },
      { label: "主題描述", before: previewText(fieldValueFromRecord(currentRecord, "brief")), after: previewText(fieldValueFromRecord(nextRecord, "brief")) },
      { label: "平台", before: previewText(fieldValueFromRecord(currentRecord, "platform")), after: previewText(fieldValueFromRecord(nextRecord, "platform")) },
    ];
    return items.filter((item) => item.before !== item.after);
  }

  if (payload.targetField === "style" && typeof next === "object" && next) {
    const currentRecord = typeof current === "object" && current && !Array.isArray(current) ? (current as Record<string, unknown>) : {};
    const nextRecord = next as Record<string, unknown>;
    const items = [
      { label: "文風標題", before: previewText(fieldValueFromRecord(currentRecord, "title")), after: previewText(fieldValueFromRecord(nextRecord, "title")) },
      { label: "層級", before: previewText(fieldValueFromRecord(currentRecord, "level")), after: previewText(fieldValueFromRecord(nextRecord, "level")) },
      { label: "平台", before: previewText(fieldValueFromRecord(currentRecord, "platform")), after: previewText(fieldValueFromRecord(nextRecord, "platform")) },
      { label: "文風內容", before: previewText(fieldValueFromRecord(currentRecord, "content")), after: previewText(fieldValueFromRecord(nextRecord, "content")) },
    ];
    return items.filter((item) => item.before !== item.after);
  }

  if (payload.targetField === "schedule") {
    return [
      {
        label: "排程內容",
        before: previewText(current),
        after: previewText(next),
      },
    ];
  }

  return [
    {
      label: field.fieldLabel,
      before: previewText(current),
      after: previewText(next),
    },
  ].filter((item) => item.before !== item.after);
}

export function CoworkChatSheet({
  campaignId,
  onUseOutput,
  onError,
  launcherLabel = "AI 討論（Beta）",
  fieldContext,
  promptContext,
  open: controlledOpen,
  onOpenChange,
  hideTrigger = false,
  desktopInline = false,
  inlineOnly = false,
}: {
  campaignId: string | null;
  onUseOutput?: (output: string) => void;
  onError: (message: string) => void;
  launcherLabel?: string;
  fieldContext?: FieldDiscussionConfig;
  promptContext?: PromptDraftDiscussionConfig;
  open?: boolean;
  onOpenChange?: (nextOpen: boolean) => void;
  hideTrigger?: boolean;
  desktopInline?: boolean;
  inlineOnly?: boolean;
}) {
  const generateHelperToken = () =>
    `mk-${Math.random().toString(36).slice(2, 8)}${Math.random().toString(36).slice(2, 8)}`;
  const effectiveCampaignId = campaignId || "global";
  const conversationScope = promptContext ? `prompt-${promptContext.skill}` : fieldContext?.fieldId || "general";
  const startedStorageKey = `zenos.copilot.started.${effectiveCampaignId}.${conversationScope}`;
  const legacyStartedStorageKey = `zenos.marketing.cowork.started.${effectiveCampaignId}.${conversationScope}`;
  const { partner: chatPartner, user: authUser } = useAuth();
  const allowedOrigins = "https://zenos-naruvia.web.app";
  const helperInstallCommand = "curl -fsSL https://zenos-naruvia.web.app/installers/install-claude-code-helper-macos.sh | bash";
  const [helperBaseUrl, setHelperBaseUrlState] = useState(getDefaultHelperBaseUrl());
  const [helperToken, setHelperTokenState] = useState(getDefaultHelperToken() || generateHelperToken());
  const [helperCwd, setHelperCwdState] = useState(getDefaultHelperCwd());
  const [helperModel, setHelperModelState] = useState(getDefaultHelperModel());
  const zenosApiKey = chatPartner?.apiKey || "<your_api_key>";
  const helperSecureStartCommand = `cd ~/.zenos/claude-code-helper && \\
ZENOS_API_KEY="${zenosApiKey}" \\
ALLOWED_ORIGINS="${allowedOrigins}" \\
LOCAL_HELPER_TOKEN="${helperToken || "<your_token>"}" \\
ALLOWED_CWDS="$HOME/.zenos/claude-code-helper/workspace" \\
node server.mjs`;
  const [internalOpen, setInternalOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [healthText, setHealthText] = useState("未檢查");
  const [running, setRunning] = useState(false);
  const [chatStatus, setChatStatus] = useState<ChatStatus>("idle");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [streamingOutput, setStreamingOutput] = useState("");
  const [currentToolUse, setCurrentToolUse] = useState<string | null>(null);
  const [capability, setCapability] = useState<CoworkCapabilityCheck | null>(null);
  const [applyPayload, setApplyPayload] = useState<StructuredApplyPayload | null>(null);
  const [missingApplyKeys, setMissingApplyKeys] = useState<string[]>([]);
  const [lastSubmittedPrompt, setLastSubmittedPrompt] = useState("");
  const [canRetry, setCanRetry] = useState(false);
  const chatViewportRef = useRef<HTMLDivElement | null>(null);
  const [hasStartedConversation, setHasStartedConversation] = useState(false);
  const [copiedInstall, setCopiedInstall] = useState(false);
  const [copiedSecureStart, setCopiedSecureStart] = useState(false);
  const [showSetupGuide, setShowSetupGuide] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [graphContext, setGraphContext] = useState<GraphContextResponse | null>(null);
  const graphContextRef = useRef<GraphContextResponse | null>(null);
  const [graphContextUnavailableReason, setGraphContextUnavailableReason] = useState<string | null>(null);
  const baselineConflictVersionRef = useRef<string | null>(null);
  const isControlled = typeof controlledOpen === "boolean";
  const open = isControlled ? controlledOpen : internalOpen;
  const railVisible = inlineOnly || desktopInline || open;
  const setOpen = useCallback(
    (nextOpen: boolean) => {
      if (!isControlled) {
        setInternalOpen(nextOpen);
      }
      onOpenChange?.(nextOpen);
    },
    [isControlled, onOpenChange]
  );
  const activeContextLabel = promptContext ? `${promptContext.title} Draft` : fieldContext?.fieldLabel;
  const activeApplyHandler = promptContext?.onApply || fieldContext?.onApply;
  const activeConflictVersion = promptContext?.draftUpdatedAt || fieldContext?.conflictVersion || null;
  const activeConflictLabel = promptContext ? `${promptContext.title} Draft` : fieldContext?.conflictLabel || fieldContext?.fieldLabel || "目前內容";

  useEffect(() => {
    const started = Boolean(readFreshSessionStartedAt(startedStorageKey, [legacyStartedStorageKey]));
    setHasStartedConversation(started);
  }, [legacyStartedStorageKey, startedStorageKey]);

  useEffect(() => {
    const el = chatViewportRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [logLines, streamingOutput]);

  useEffect(() => {
    setLogLines([]);
    setStreamingOutput("");
    setApplyPayload(null);
    setMissingApplyKeys([]);
    setChatStatus("idle");
    setRequestId(null);
    setCanRetry(false);
    graphContextRef.current = null;
    setGraphContext(null);
    setGraphContextUnavailableReason(null);
    baselineConflictVersionRef.current = activeConflictVersion;
  }, [effectiveCampaignId, conversationScope]);

  useEffect(() => {
    if (!railVisible || healthText !== "未檢查") return;
    void runHealthCheck();
  }, [railVisible]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-retry health check every 5s when sheet is open but helper is disconnected
  useEffect(() => {
    if (!railVisible || healthText === "可連線" || checkingHealth || running) return;
    const timer = setInterval(() => {
      void runHealthCheck();
    }, 5000);
    return () => clearInterval(timer);
  }, [railVisible, healthText, checkingHealth, running]); // eslint-disable-line react-hooks/exhaustive-deps

  const conversationId = `marketing-${effectiveCampaignId}-${conversationScope}`;
  const contextPack = useMemo(
    () => {
      if (promptContext) {
        return {
          target: "marketing_prompt_draft",
          skill: promptContext.skill,
          title: promptContext.title,
          project_summary: promptContext.projectSummary,
          published_version: promptContext.publishedVersion,
          published_content: promptContext.publishedContent,
          draft_content: promptContext.draftContent,
        };
      }
      return fieldContext
        ? buildContextPack({
            fieldId: fieldContext.fieldId,
            currentPhase: fieldContext.currentPhase,
            suggestedSkill: fieldContext.suggestedSkill,
            projectSummary: fieldContext.projectSummary,
            fieldValue: fieldContext.fieldValue,
            relatedContext: fieldContext.relatedContext,
          })
        : null;
    },
    [fieldContext, promptContext]
  );
  const runtimeContextPack = useMemo(() => {
    if (!fieldContext || fieldContext.fieldId !== "strategy" || !contextPack) {
      return contextPack;
    }
    return {
      ...contextPack,
      seed_entity: campaignId,
      target_fields: MARKETING_STRATEGY_TARGET_FIELDS,
      graph_context: graphContext,
    };
  }, [campaignId, contextPack, fieldContext, graphContext]);
  const promptPreview = useMemo(() => {
    if (promptContext) {
      return buildPromptDraftDiscussionPrompt(promptContext, prompt.trim());
    }
    if (fieldContext) {
      return fieldContext.fieldId === "strategy"
        ? buildMarketingKnowledgePrompt(fieldContext, prompt.trim(), {
            graphContext,
            targetFields: MARKETING_STRATEGY_TARGET_FIELDS,
          })
        : buildDiscussionPrompt(fieldContext, prompt.trim());
    }
    return prompt.trim() || "尚未輸入訊息";
  }, [fieldContext, graphContext, prompt, promptContext]);
  const shellEntry = useMemo<CopilotEntryConfig>(() => {
    const title = promptContext
      ? `討論 Prompt：${promptContext.title}`
      : fieldContext
        ? `討論這段：${fieldContext.fieldLabel}`
        : "Marketing AI Rail";
    const scopeLabel = promptContext
      ? `${promptContext.title} / draft`
      : fieldContext
        ? `${fieldContext.fieldLabel} / 已載入範圍`
        : "全域對話";
    return {
      intent_id: promptContext
        ? `marketing.prompt.${promptContext.skill}`
        : fieldContext
          ? `marketing.${fieldContext.fieldId}`
          : "marketing.general",
      title,
      mode: activeApplyHandler ? "apply" : "chat",
      launch_behavior: "manual" as const,
      session_policy: "scoped_resume" as const,
      suggested_skill: promptContext ? promptContext.skill : fieldContext?.suggestedSkill,
      claude_code_bootstrap: {
        use_project_claude_config: true,
        required_skills: [
          promptContext ? promptContext.skill : fieldContext?.suggestedSkill || "/marketing-plan",
          "/zenos-governance",
          "skills/governance/task-governance.md",
          "skills/governance/document-governance.md",
        ].filter(Boolean),
        governance_topics: ["task", "document"],
        verify_zenos_write: true,
        execution_contract: [
          "Operate as Claude Code CLI with the workspace-local .claude MCP/settings files.",
          "Treat marketing writes as governed ZenOS mutations: read task/document governance before creating or updating records.",
          "If the requested work has ordered multi-step execution, create a plan first and attach every generated task with plan_id plus plan_order instead of using parent tasks as pseudo-plans.",
          "After any claimed ZenOS write, re-fetch the saved record before telling the user it is complete.",
        ],
      },
      scope: {
        workspace_id: resolveCopilotWorkspaceId(chatPartner),
        campaign_id: campaignId || undefined,
        entity_ids: campaignId ? [campaignId] : undefined,
        scope_label: scopeLabel,
      },
      context_pack: runtimeContextPack || {},
      write_targets: activeApplyHandler ? [promptContext ? "marketing_prompt_draft" : fieldContext?.fieldId || "general"] : undefined,
      build_prompt: (input: string) =>
        promptContext
          ? buildPromptDraftDiscussionPrompt(promptContext, input)
          : fieldContext
            ? fieldContext.fieldId === "strategy"
              ? buildMarketingKnowledgePrompt(fieldContext, input, {
                  graphContext: graphContextRef.current,
                  targetFields: MARKETING_STRATEGY_TARGET_FIELDS,
                })
              : buildDiscussionPrompt(fieldContext, input)
            : input,
    };
  }, [activeApplyHandler, campaignId, fieldContext, promptContext, runtimeContextPack]);
  const statusText = {
    idle: "等待輸入",
    loading: "初始化中",
    streaming: "AI 回覆中",
    "awaiting-local-approval": "等待本機確認",
    "apply-ready": "可套用",
    applying: "寫回中",
    error: "需要修復",
  } as const;

  const updateConversationStarted = (started: boolean) => {
    if (started) {
      markSessionStarted(startedStorageKey, [legacyStartedStorageKey]);
    } else {
      clearSessionStarted(startedStorageKey, [legacyStartedStorageKey]);
    }
    setHasStartedConversation(started);
  };

  const persistHelperSettings = () => {
    setDefaultHelperBaseUrl(helperBaseUrl);
    setDefaultHelperToken(helperToken);
    setDefaultHelperCwd(helperCwd);
    setDefaultHelperModel(helperModel);
  };

  const runHealthCheck = async () => {
    setCheckingHealth(true);
    persistHelperSettings();
    const health = await checkCoworkHelperHealth(helperBaseUrl, helperToken);
    if (!health) {
      setCapability(null);
      setHealthText("不可用：helper unavailable");
      setCheckingHealth(false);
      return;
    }
    setCapability(health.capability || null);
    setHealthText(health.ok ? "可連線" : `不可用：${health.message || health.status}`);
    setCheckingHealth(false);
  };

  const ensureGraphContext = useCallback(async (): Promise<GraphContextResponse | null> => {
    if (!fieldContext || !campaignId || fieldContext.fieldId !== "strategy" || !authUser) {
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
    const authToken = await authUser.getIdToken();
    const nextGraphContext = await fetchGraphContext(authToken, {
      seedId: campaignId,
    });
    graphContextRef.current = nextGraphContext;
    setGraphContext(nextGraphContext);
    setGraphContextUnavailableReason(nextGraphContext ? null : graphContextUnavailableNotice());
    return nextGraphContext;
  }, [authUser, campaignId, capability, fieldContext]);

  const sendMessage = async (promptOverride?: string) => {
    const promptInput = typeof promptOverride === "string" ? promptOverride : prompt;
    const userPrompt = promptInput.trim();
    if (running || (!userPrompt && !fieldContext && !promptContext)) return;
    const nextGraphContext = promptContext ? null : await ensureGraphContext();
    const effectivePrompt = promptContext
      ? buildPromptDraftDiscussionPrompt(promptContext, userPrompt)
      : fieldContext
        ? fieldContext.fieldId === "strategy"
          ? buildMarketingKnowledgePrompt(fieldContext, userPrompt, {
              graphContext: nextGraphContext,
              targetFields: MARKETING_STRATEGY_TARGET_FIELDS,
            })
          : buildDiscussionPrompt(fieldContext, userPrompt)
        : userPrompt;
    persistHelperSettings();
    setPrompt("");
    setLastSubmittedPrompt(userPrompt);
    setCanRetry(true);
    setRunning(true);
    setChatStatus((prev) => nextChatStatus(prev, "send"));
    setRequestId(null);
    setStreamingOutput("");
    setApplyPayload(null);
    setMissingApplyKeys([]);
    setLogLines((prev) => [...prev, `你：${userPrompt}`]);

    const runOnce = async (mode: "start" | "continue") => {
      let collected = "";
      let stderrCombined = "";
      let exitCode: number | null = null;
      await streamCoworkChat({
        baseUrl: helperBaseUrl,
        token: helperToken,
        mode,
        conversationId,
        prompt: effectivePrompt,
        model: helperModel,
        cwd: helperCwd,
        maxTurns: COWORK_MAX_TURNS,
        onEvent: (event: CoworkStreamEvent) => {
          if ("requestId" in event && event.requestId && !requestId) setRequestId(event.requestId);
          if (event.type === "capability_check") {
            setCapability(event.capability);
            if (!event.capability.mcpOk) {
              setLogLines((prev) => [...prev, "系統：ZenOS 連線失敗，這輪仍可對話但無法讀寫資料。"]);
            }
            const missingSkills = event.capability.missingSkills || [];
            if (missingSkills.length > 0) {
              setLogLines((prev) => [...prev, `系統：部分 skill 未載入：${missingSkills.join(", ")}`]);
            }
            return;
          }
          if (event.type === "permission_request") {
            setChatStatus((prev) => nextChatStatus(prev, "permission_request"));
            const toolLabel = event.request?.toolName || "工具";
            setCurrentToolUse(`等待授權：${toolLabel}`);
            setLogLines((prev) => [...prev, `系統：等待本機 terminal 確認 ${toolLabel}（${event.request?.timeoutSeconds || 30} 秒）`]);
            return;
          }
          if (event.type === "permission_result") {
            const toolLabel = event.result?.toolName || "工具";
            const approved = event.result?.approved;
            setCurrentToolUse(approved ? null : `授權被拒：${toolLabel}`);
            setLogLines((prev) => [...prev, `系統：${toolLabel} ${approved ? "已核准" : `已拒絕（${event.result?.reason || "unknown"}）`}`]);
            setChatStatus((prev) => nextChatStatus(prev, "permission_result"));
            return;
          }
          if (event.type === "stderr") {
            const text = event.text.trim();
            if (text) {
              stderrCombined += `${stderrCombined ? "\n" : ""}${text}`;
              setLogLines((prev) => [...prev, `系統：${text}`]);
            }
            return;
          }
          if (event.type === "message") {
            setChatStatus((prev) => nextChatStatus(prev, "message"));
            const parsed = parseCoworkStreamLine(event.line);
            if (parsed.delta) {
              collected += parsed.delta;
              setStreamingOutput(collected);
              setCurrentToolUse(null);
              return;
            }
            if (parsed.toolUse) {
              setCurrentToolUse(parsed.toolUse);
              return;
            }
            if (parsed.debug) {
              setLogLines((prev) => [...prev, `系統：${parsed.debug}`]);
            }
            return;
          }
          if (event.type === "done") {
            setCurrentToolUse(null);
            if (typeof event.code === "number") {
              exitCode = event.code;
            }
            if (collected.trim()) {
              setLogLines((prev) => [...prev, `Claude：${collected.trim()}`]);
              const { payload, missingKeys } = parseStructuredApplyPayload(
                collected.trim(),
                promptContext ? "marketing_prompt_draft" : fieldContext?.fieldId
              );
              if (payload && activeApplyHandler) {
                setApplyPayload(payload);
                setChatStatus((prev) => nextChatStatus(prev, "apply_available"));
              } else {
                setChatStatus((prev) => nextChatStatus(prev, "reset"));
              }
              if (missingKeys.length > 0) {
                setMissingApplyKeys(missingKeys);
              }
              if (!payload) {
                onUseOutput?.(collected.trim());
              }
            } else if (chatStatus !== "error") {
              setChatStatus((prev) => nextChatStatus(prev, "reset"));
            }
          }
          if (event.type === "error") {
            setChatStatus((prev) => nextChatStatus(prev, "error"));
            setLogLines((prev) => [...prev, `系統：${event.message}`]);
          }
        },
      });

      if (exitCode !== null && exitCode !== 0) {
        throw new Error(stderrCombined || `Claude Code CLI exited with code ${exitCode}`);
      }
    };

    try {
      const canResumeConversation = Boolean(readFreshSessionStartedAt(startedStorageKey, [legacyStartedStorageKey]));
      if (!canResumeConversation && hasStartedConversation) {
        setHasStartedConversation(false);
      }

      if (canResumeConversation) {
        try {
          await runOnce("continue");
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          if (/not found|session/i.test(msg)) {
            updateConversationStarted(false);
            await runOnce("start");
            updateConversationStarted(true);
          } else {
            throw err;
          }
        }
      } else {
        await runOnce("start");
        updateConversationStarted(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "呼叫 Claude Code CLI 失敗";
       setChatStatus((prev) => nextChatStatus(prev, "error"));
      setLogLines((prev) => [...prev, `系統：${msg}`]);
      onError(msg);
    } finally {
      setRunning(false);
      setStreamingOutput("");
      setRequestId(null);
    }
  };

  const handleCancel = async () => {
    if (!running) return;
    try {
      await cancelCoworkRequest({
        baseUrl: helperBaseUrl,
        token: helperToken,
        requestId: requestId || undefined,
        conversationId,
      });
      setLogLines((prev) => [...prev, "系統：已送出取消請求"]);
      setChatStatus((prev) => nextChatStatus(prev, "cancel"));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "取消失敗";
      setLogLines((prev) => [...prev, `系統：${msg}`]);
      setChatStatus((prev) => nextChatStatus(prev, "error"));
      onError(msg);
    }
  };

  const handleApply = async () => {
    if (!applyPayload || !activeApplyHandler) return;
    try {
      const baselineVersion = baselineConflictVersionRef.current;
      const currentVersion = activeConflictVersion;
      if (baselineVersion && currentVersion && baselineVersion !== currentVersion) {
        const shouldOverwrite = window.confirm(
          `${activeConflictLabel} 在你對話期間已被其他來源更新。按「確定」覆蓋，按「取消」放棄套用。`
        );
        if (!shouldOverwrite) {
          setLogLines((prev) => [...prev, `系統：已放棄套用，因為 ${activeConflictLabel} 發生衝突。`]);
          setChatStatus((prev) => nextChatStatus(prev, "cancel"));
          setApplyPayload(null);
          return;
        }
      }
      setChatStatus((prev) => nextChatStatus(prev, "apply_start"));
      await activeApplyHandler(applyPayload);
      setLogLines((prev) => [...prev, `系統：已套用到 ${applyPayload.targetField}`]);
      setApplyPayload(null);
      setMissingApplyKeys([]);
      baselineConflictVersionRef.current = currentVersion || baselineConflictVersionRef.current;
      setChatStatus((prev) => nextChatStatus(prev, "apply_done"));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "套用失敗";
      setLogLines((prev) => [...prev, `系統：${msg}`]);
      setChatStatus((prev) => nextChatStatus(prev, "error"));
      onError(msg);
    }
  };

  const helperUnavailable = healthText.startsWith("不可用");
  const helperConnected = healthText === "可連線";
  const helperStatusTone = helperUnavailable
    ? "border-destructive/35 bg-destructive/12 text-red-200"
    : helperConnected
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
      : "border-border/40 bg-background/70 text-muted-foreground";
  const hasCapabilityWarnings = Boolean(
    capability && (!capability.mcpOk || (capability.missingSkills && capability.missingSkills.length > 0))
  );
  const changePreview = useMemo(
    () => buildApplyChangePreview(fieldContext, promptContext, applyPayload),
    [applyPayload, fieldContext, promptContext]
  );
  const canSummarize = !running && (logLines.length > 0 || hasStartedConversation);
  const userTurnCount = logLines.filter((line) => line.startsWith("你：")).length;
  const turnLimitReached = userTurnCount >= COWORK_MAX_TURNS;
  const compactPreviewText = (value: string, max = 88) => {
    const normalized = value.replace(/\s+/g, " ").trim();
    if (normalized.length <= max) return normalized;
    return `${normalized.slice(0, max - 1)}…`;
  };
  const handleRailOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (nextOpen) {
      baselineConflictVersionRef.current = activeConflictVersion;
      return;
    }
    setChatStatus((prev) => nextChatStatus(prev, "reset"));
    setApplyPayload(null);
    setMissingApplyKeys([]);
    setPrompt("");
    setStreamingOutput("");
    setCanRetry(false);
  };

  return (
    <>
      {!hideTrigger && (
        <Button
          size="sm"
          variant="outline"
          className="h-7 gap-1.5 text-[11px]"
          onClick={() => handleRailOpenChange(true)}
        >
          <PlugZap className="h-3.5 w-3.5" />
          {launcherLabel}
        </Button>
      )}
      <CopilotRailShell
        open={open}
        onOpenChange={handleRailOpenChange}
        entry={shellEntry}
        chatStatus={chatStatus}
        connectorStatus={checkingHealth ? "checking" : helperConnected ? "connected" : "disconnected"}
        desktopInline={desktopInline}
        inlineOnly={inlineOnly}
        diagnostics={
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium text-foreground">
                {activeContextLabel ? `正在處理 ${activeContextLabel}` : "先從任一區塊把內容帶進 AI"}
              </div>
              <div className="mt-1 text-[11px] text-muted-foreground">
                {applyPayload
                  ? "AI 已整理出可套用摘要，先看變更，再決定要不要寫回。"
                  : activeApplyHandler
                    ? "直接描述你想修改的方向，AI 會整理成可預覽的變更。"
                    : "保留最必要的上下文與操作，不再把診斷資訊攤滿整個面板。"}
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              className={`h-7 gap-1.5 text-[11px] ${helperStatusTone}`}
              onClick={() => {
                setShowDiagnostics((v) => (helperUnavailable ? true : !v));
                if (helperUnavailable) setShowSetupGuide(true);
              }}
            >
              <PlugZap className="h-3.5 w-3.5" />
              {checkingHealth ? "Connector 檢查中" : helperConnected ? "Connector 已連線" : "Connector 未連線"}
            </Button>
          </div>
        }
        footer={
          <div>
            {missingApplyKeys.length > 0 && (
              <div className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-100">
                AI 回覆還不能套用，缺少欄位：{missingApplyKeys.join(", ")}
              </div>
            )}

            {chatStatus === "error" && (
              <div className="mb-3 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                對話中斷或寫回失敗。可先修復 helper / 連線後，再重試上一輪。
              </div>
            )}

            {applyPayload && chatStatus === "apply-ready" && (
              <div className="mb-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-xs font-medium text-foreground">可套用到 {activeContextLabel || applyPayload.targetField}</div>
                  <Badge variant="outline" className="text-[10px] border-emerald-500/20 bg-emerald-500/10 text-emerald-100">
                    {changePreview.length} 項變更
                  </Badge>
                </div>
                {changePreview.length > 0 && (
                  <div className="mb-3 space-y-2">
                    {changePreview.map((item) => (
                      <div key={item.label} className="rounded-md border border-border/30 bg-background/70 px-3 py-2">
                        <div className="mb-1 text-[11px] font-medium text-foreground">{item.label}</div>
                        <div className="grid gap-1 text-[11px] sm:grid-cols-[1fr_auto_1fr] sm:items-start sm:gap-2">
                          <div className="rounded border border-border/20 bg-card/50 px-2 py-1.5 text-muted-foreground">
                            {compactPreviewText(item.before)}
                          </div>
                          <div className="hidden pt-1 text-muted-foreground sm:block">→</div>
                          <div className="rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1.5 text-foreground">
                            {compactPreviewText(item.after)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <details className="rounded-md border border-border/20 bg-background/40 px-3 py-2">
                  <summary className="cursor-pointer text-[11px] font-medium text-muted-foreground">查看原始 structured result</summary>
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] text-muted-foreground">
                    {typeof applyPayload.value === "string" ? applyPayload.value : JSON.stringify(applyPayload.value, null, 2)}
                  </pre>
                </details>
              </div>
            )}

            <div className="mb-3 text-xs text-muted-foreground">
              {activeApplyHandler
                ? "先討論，再看變更摘要，最後決定是否寫回。"
                : onUseOutput
                  ? "回覆完成後會自動帶回到目前流程。"
                  : "可自由聊，也可先從左側把設定帶進來。"}
            </div>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={activeContextLabel ? `直接說你想怎麼改 ${activeContextLabel}` : "直接輸入要討論的內容"}
              className="min-h-[60px] w-full resize-none rounded-xl border border-border/50 bg-muted/30 px-4 py-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/50 focus:border-primary/50 focus:bg-muted/50"
            />

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs text-muted-foreground">{running ? "Claude 正在回覆" : "Enter 換行"}</div>
              <div className="flex flex-wrap items-center gap-2">
                {canSummarize && activeContextLabel && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={() =>
                      void sendMessage(
                        `請根據目前對話整理成可直接套用到 ${activeContextLabel} 的結構化結果。請先簡短總結，再輸出符合 target_field/value 契約的 JSON。`
                      )
                    }
                  >
                    整理結果
                  </Button>
                )}
                {chatStatus === "error" && canRetry && (
                  <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => void sendMessage(lastSubmittedPrompt)}>
                    重試上一輪
                  </Button>
                )}
                {applyPayload && chatStatus === "apply-ready" && (
                  <Button size="sm" className="h-8 text-xs" onClick={handleApply}>
                    套用到欄位
                  </Button>
                )}
                {running && (
                  <Button size="sm" variant="outline" className="h-8 text-xs" onClick={handleCancel}>
                    停止
                  </Button>
                )}
                <Button
                  size="sm"
                  className="h-8 text-xs"
                  disabled={
                    running ||
                    chatStatus === "applying" ||
                    helperUnavailable ||
                    turnLimitReached ||
                    (!fieldContext && !promptContext && !prompt.trim())
                  }
                  onClick={() => void sendMessage()}
                >
                  {running ? "執行中..." : helperUnavailable ? "先連線 Connector" : activeContextLabel ? "開始討論" : "送出"}
                </Button>
              </div>
            </div>
            {turnLimitReached && (
              <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                已達對話上限，請整理當前結果或開啟新 session。
              </div>
            )}
          </div>
        }
      >
          <div className="space-y-3">
            <div className="rounded-2xl border border-border/30 bg-card/45 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground">
                    {activeContextLabel ? `討論這段：${activeContextLabel}` : "AI 工作區"}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {activeContextLabel
                      ? "只保留目前欄位、project scope 和必要 context，討論完直接看變更摘要。"
                      : "先從任一區塊按「帶進 AI」，再開始討論。"}
                  </p>
                </div>
                {activeApplyHandler && (
                  <Badge
                    variant="outline"
                    className="shrink-0 border-emerald-500/20 bg-emerald-500/10 text-[10px] text-emerald-100"
                  >
                    可套用
                  </Badge>
                )}
              </div>
              <div className="mt-3">
                <GraphContextBadge
                  className="w-full"
                  compact
                  graphContext={graphContext}
                  unavailableReason={graphContextUnavailableReason}
                />
              </div>
            </div>

            {hasCapabilityWarnings && capability && (
              <div className="flex flex-wrap gap-2 text-[11px]">
                {!capability.mcpOk && (
                  <div className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-amber-200">
                    ZenOS 連線失敗，這輪只能對話不能寫回
                  </div>
                )}
                {capability.missingSkills && capability.missingSkills.length > 0 && (
                  <div className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-amber-200">
                    缺 skill：{capability.missingSkills.join(", ")}
                  </div>
                )}
              </div>
            )}

            <details className="rounded-xl border border-border/20 bg-background/60 p-3">
              <summary className="cursor-pointer text-xs font-medium text-foreground">查看 prompt / context</summary>
              <div className="mt-3 grid gap-3">
                {runtimeContextPack && (
                  <div className="rounded-lg border border-border/20 bg-background/60 p-3">
                    <div className="mb-2 text-[11px] font-medium text-foreground">已載入上下文清單</div>
                    <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-muted-foreground">
                      {JSON.stringify(runtimeContextPack, null, 2)}
                    </pre>
                  </div>
                )}
                <div className="rounded-lg border border-border/20 bg-background/60 p-3">
                  <div className="mb-2 text-[11px] font-medium text-foreground">Prompt 預覽</div>
                  <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-muted-foreground">{promptPreview}</pre>
                </div>
              </div>
            </details>

          {showDiagnostics && (
            <div className="space-y-3 rounded-xl border border-border/40 bg-card/60 p-3">
              <div className="flex items-center justify-between">
                <div className="text-xs font-medium text-foreground">Connector 設定</div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-[10px]"
                    disabled={checkingHealth}
                    onClick={runHealthCheck}
                  >
                    {checkingHealth ? "檢查中..." : "重新檢查"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-[10px]"
                    onClick={() => setShowSetupGuide((v) => !v)}
                  >
                    {showSetupGuide ? "收起引導" : "設定引導"}
                  </Button>
                </div>
              </div>

              {showSetupGuide && (
                <div className="space-y-2 text-[11px]">
                  <div className="rounded border border-border/30 bg-background/70 p-2">
                    <div className="mb-1 text-muted-foreground">1. 安裝 Connector helper</div>
                    <code className="block overflow-x-auto whitespace-nowrap text-foreground">{helperInstallCommand}</code>
                    <div className="mt-2 flex justify-end">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 px-2 text-[10px]"
                        onClick={async () => {
                          await navigator.clipboard.writeText(helperInstallCommand);
                          setCopiedInstall(true);
                          setTimeout(() => setCopiedInstall(false), 1200);
                        }}
                      >
                        {copiedInstall ? "已複製" : "複製安裝指令"}
                      </Button>
                    </div>
                  </div>
                  <div className="rounded border border-border/30 bg-background/70 p-2">
                    <div className="mb-1 text-muted-foreground">2. 貼 token 並啟動</div>
                    <input
                      value={helperToken}
                      onChange={(e) => setHelperTokenState(e.target.value)}
                      placeholder="貼一組 token（例如公司提供給你的）"
                      className="mb-2 h-8 w-full rounded-md border border-border/50 bg-background px-2.5 text-xs text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                    />
                    <code className="block overflow-x-auto whitespace-nowrap text-foreground">{helperSecureStartCommand}</code>
                    <div className="mt-2 flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 px-2 text-[10px]"
                        onClick={() => setHelperTokenState(generateHelperToken())}
                      >
                        產生新 token
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 px-2 text-[10px]"
                        onClick={async () => {
                          await navigator.clipboard.writeText(helperSecureStartCommand);
                          setCopiedSecureStart(true);
                          setTimeout(() => setCopiedSecureStart(false), 1200);
                        }}
                      >
                        {copiedSecureStart ? "已複製" : "複製啟動指令"}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              <div className="grid gap-2 sm:grid-cols-[140px_1fr] sm:items-center">
                <label className="text-[11px] text-muted-foreground">模型</label>
                <select
                  value={helperModel}
                  onChange={(e) => setHelperModelState(e.target.value)}
                  className="h-8 rounded-md border border-border/50 bg-background px-2 text-[11px] text-foreground outline-none focus:border-primary/50"
                >
                  <option value="sonnet">Sonnet（預設）</option>
                  <option value="opus">Opus</option>
                  <option value="haiku">Haiku</option>
                </select>
              </div>

              <div className="flex items-center justify-between rounded border border-border/30 bg-background/70 px-2 py-1.5">
                <span className="text-[11px] text-muted-foreground">進階設定（URL / CWD）</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => setShowAdvancedSettings((v) => !v)}
                >
                  {showAdvancedSettings ? "收起" : "展開"}
                </Button>
              </div>

              {showAdvancedSettings && (
                <div className="grid gap-2">
                  <input
                    value={helperBaseUrl}
                    onChange={(e) => setHelperBaseUrlState(e.target.value)}
                    placeholder="Helper URL（預設 http://127.0.0.1:4317）"
                    className="h-8 rounded-md border border-border/50 bg-background px-2.5 text-xs text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                  />
                  <input
                    value={helperCwd}
                    onChange={(e) => setHelperCwdState(e.target.value)}
                    placeholder="專案路徑 cwd（選填）"
                    className="h-8 rounded-md border border-border/50 bg-background px-2.5 text-xs text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                  />
                </div>
              )}
            </div>
          )}

          <div className="flex min-h-[360px] flex-col">
            <div className="mb-2 flex shrink-0 items-center justify-between">
              <div className="text-sm font-medium text-foreground">對話</div>
              <Badge variant="outline" className="text-[10px]">
                {running ? "串流中" : helperConnected ? "可聊天" : "待連線"}
              </Badge>
            </div>
            <div
              ref={chatViewportRef}
              className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto rounded-[24px] border border-white/10 bg-black/20 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
            >
              {logLines.length === 0 ? (
                <div className="m-auto max-w-md text-center">
                  <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                    <Bot className="h-5 w-5 text-foreground" />
                  </div>
                  <div className="text-sm font-medium text-foreground">
                    {activeContextLabel ? `已載入 ${activeContextLabel}` : helperConnected ? "先選一段內容帶進 AI" : "先連上 Connector"}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {activeContextLabel ? "直接描述你要調整的方向，整理後可預覽 diff 再套用。" : "策略、排程、文風、主題與 prompt draft 都會沿用同一套使用方式。"}
                  </div>
                </div>
              ) : (
                logLines.map((line, index) => {
                  const isUser = line.startsWith("你：");
                  const isAssistant = line.startsWith("Claude：");
                  const content = line.replace(/^(你|Claude|系統)：\s*/, "");
                  return (
                    <div key={`${index}-${line.slice(0, 20)}`} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm shadow-sm ${
                          isUser
                            ? "bg-primary/20 text-foreground"
                            : isAssistant
                              ? "border border-emerald-500/20 bg-emerald-500/10 text-foreground"
                              : "border border-white/8 bg-white/5 text-muted-foreground"
                        }`}
                      >
                        {isAssistant ? (
                          <MarkdownRenderer content={content} className="text-sm text-foreground space-y-1" />
                        ) : (
                          content
                        )}
                      </div>
                    </div>
                  );
                })
              )}
              {running && streamingOutput && (
                <div className="flex justify-start">
                  <div className="max-w-[88%] whitespace-pre-wrap rounded-2xl border border-emerald-500/15 bg-emerald-500/8 px-4 py-3 text-sm text-foreground">
                    <MarkdownRenderer content={streamingOutput} className="text-sm text-foreground space-y-1" />
                    <span className="ml-1 inline-block h-3 w-1 animate-pulse rounded bg-foreground/60 align-middle" />
                  </div>
                </div>
              )}
              {running && currentToolUse && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-muted-foreground">
                    <span className="inline-block h-2 w-2 animate-spin rounded-full border border-muted-foreground/40 border-t-muted-foreground" />
                    {currentToolUse}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </CopilotRailShell>
    </>
  );
}

export function StrategyPlanner({
  campaign,
  strategy,
  onSave,
  onError,
  saving,
  onOpenCopilot,
}: {
  campaign: Campaign;
  strategy?: Strategy;
  onSave: (input: {
    audience: string[];
    tone: string;
    coreMessage: string;
    platforms: string[];
    frequency?: string;
    contentMix?: Record<string, number>;
    campaignGoal?: string;
    ctaStrategy?: string;
    referenceMaterials?: string[];
    pendingFields?: string[];
    sourceCitations?: Array<{ node_id: string; node_name: string; field_ids?: string[] }>;
    confidence?: "high" | "medium" | "low";
  }) => Promise<void>;
  onError: (message: string) => void;
  saving: boolean;
  onOpenCopilot?: (config: FieldDiscussionConfig) => void;
}) {
  const [audience, setAudience] = useState(formatCsv(strategy?.audience));
  const [tone, setTone] = useState(strategy?.tone || "");
  const [coreMessage, setCoreMessage] = useState(strategy?.coreMessage || "");
  const [platforms, setPlatforms] = useState(formatCsv(strategy?.platforms));
  const [frequency, setFrequency] = useState(strategy?.frequency || "");
  const [contentMix, setContentMix] = useState(formatContentMix(strategy?.contentMix));
  const [campaignGoal, setCampaignGoal] = useState(strategy?.campaignGoal || "");
  const [ctaStrategy, setCtaStrategy] = useState(strategy?.ctaStrategy || "");
  const [referenceMaterials, setReferenceMaterials] = useState(formatCsv(strategy?.referenceMaterials));
  const [showManual, setShowManual] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  useEffect(() => {
    setAudience(formatCsv(strategy?.audience));
    setTone(strategy?.tone || "");
    setCoreMessage(strategy?.coreMessage || "");
    setPlatforms(formatCsv(strategy?.platforms));
    setFrequency(strategy?.frequency || "");
    setContentMix(formatContentMix(strategy?.contentMix));
    setCampaignGoal(strategy?.campaignGoal || "");
    setCtaStrategy(strategy?.ctaStrategy || "");
    setReferenceMaterials(formatCsv(strategy?.referenceMaterials));
  }, [strategy]);

  const parsedAudience = parseCsv(audience);
  const parsedPlatforms = parseCsv(platforms);
  const parsedContentMix = parseContentMix(contentMix);
  const contentMixParseError =
    campaign.projectType === "long_term" && contentMix.trim() && Object.keys(parsedContentMix).length === 0
      ? "內容比例格式讀不到。可用 education:70, product:30、education 70, product 30 或 JSON。"
      : null;
  const saveBlockers = getStrategySaveBlockers({
    projectType: campaign.projectType,
    audience: parsedAudience,
    tone,
    coreMessage,
    platforms: parsedPlatforms,
    frequency,
    contentMix: parsedContentMix,
  });
  const canSave =
    saveBlockers.length === 0 &&
    !saving;

  useEffect(() => {
    if (saveBlockers.length === 0 && parseError?.startsWith("還缺 ")) {
      setParseError(null);
    }
  }, [parseError, saveBlockers]);

  return (
    <div className="rounded-xl border border-border/40 bg-card/70 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-foreground">建立行銷寫作計畫</h3>
          <p className="mt-1 text-xs text-muted-foreground">先和 AI 討論策略，不用你手填一堆欄位。</p>
        </div>
        <CopilotLaunchButton
          onClick={() =>
            onOpenCopilot?.({
              fieldId: "strategy",
              fieldLabel: "策略設定",
              currentPhase: "strategy",
              suggestedSkill: "/marketing-plan",
              projectSummary: buildProjectSummary(campaign),
              conflictVersion: strategy?.updatedAt || null,
              conflictLabel: "策略",
              fieldValue: {
                audience: parsedAudience,
                tone,
                core_message: coreMessage,
                platforms: parsedPlatforms,
                frequency,
                content_mix: parsedContentMix,
                campaign_goal: campaignGoal,
                cta_strategy: ctaStrategy,
                reference_materials: parseCsv(referenceMaterials),
              },
              relatedContext: strategy?.summaryEntry,
              onApply: async (payload) => {
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
                const confidence = confidenceRaw === "low" || confidenceRaw === "medium" || confidenceRaw === "high"
                  ? confidenceRaw
                  : undefined;
                setAudience(formatCsv(nextAudience));
                setTone(nextTone);
                setCoreMessage(nextCoreMessage);
                setPlatforms(formatCsv(nextPlatforms));
                setFrequency(nextFrequency);
                setContentMix(formatContentMix(nextContentMix));
                setCampaignGoal(nextCampaignGoal);
                setCtaStrategy(nextCtaStrategy);
                setReferenceMaterials(formatCsv(nextReferenceMaterials));
                setShowManual(true);
                const nextSaveBlockers = getStrategySaveBlockers({
                  projectType: campaign.projectType,
                  audience: nextAudience,
                  tone: nextTone,
                  coreMessage: nextCoreMessage,
                  platforms: nextPlatforms,
                  frequency: nextFrequency,
                  contentMix: nextContentMix,
                });
                if (nextSaveBlockers.length > 0) {
                  setParseError(`還缺 ${nextSaveBlockers.join("、")}，補完後才能儲存策略。`);
                  return;
                }
                setParseError(null);
                await onSave({
                  audience: nextAudience,
                  tone: nextTone,
                  coreMessage: nextCoreMessage,
                  platforms: nextPlatforms,
                  frequency: campaign.projectType === "long_term" ? nextFrequency : undefined,
                  contentMix: campaign.projectType === "long_term" ? nextContentMix : undefined,
                  campaignGoal: nextCampaignGoal,
                  ctaStrategy: nextCtaStrategy,
                  referenceMaterials: nextReferenceMaterials,
                  pendingFields: nextPendingFields,
                  sourceCitations,
                  confidence,
                });
              },
            })
          }
        >
          先帶進 AI
        </CopilotLaunchButton>
      </div>

      <div className="rounded-md border border-border/40 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
        AI 工作區會沿用同一套對話、權限、diff 與寫回流程。策略討論完可直接套用到下方欄位。
      </div>
      {parseError && <p className="mt-1 text-xs text-destructive">{parseError}</p>}

      <button
        className="mt-2 flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => setShowManual((v) => !v)}
      >
        {showManual ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        手動微調策略（進階）
      </button>
      {showManual && (
        <>
          <div className="mt-2 grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">目標受眾</label>
                <input
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="逗號分隔"
                  className="h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">語氣風格</label>
                <input
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  placeholder="例如：專業但親切"
                  className="h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">發文平台</label>
                <input
                  value={platforms}
                  onChange={(e) => setPlatforms(e.target.value)}
                  placeholder="逗號分隔"
                  className="h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                />
              </div>
              {campaign.projectType === "long_term" && (
                <>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">發文頻率</label>
                    <input
                      value={frequency}
                      onChange={(e) => setFrequency(e.target.value)}
                      placeholder="例如每週 2 篇"
                      className="h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">內容比例</label>
                    <input
                      value={contentMix}
                      onChange={(e) => setContentMix(e.target.value)}
                      onBlur={() => {
                        if (Object.keys(parsedContentMix).length > 0) {
                          setContentMix(formatContentMix(parsedContentMix));
                        }
                      }}
                      placeholder="例如 education:70, product:30"
                      className="h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                    />
                    {contentMixParseError ? (
                      <p className="mt-1 text-[11px] text-destructive">{contentMixParseError}</p>
                    ) : contentMix.trim() && Object.keys(parsedContentMix).length > 0 ? (
                      <p className="mt-1 text-[11px] text-muted-foreground">已辨識：{formatContentMix(parsedContentMix)}</p>
                    ) : null}
                  </div>
                </>
              )}
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-muted-foreground">核心訊息</label>
              <textarea
                value={coreMessage}
                onChange={(e) => setCoreMessage(e.target.value)}
                placeholder="品牌想傳達的核心價值"
                className="min-h-[48px] w-full resize-y rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-muted-foreground">活動目標</label>
              <textarea
                value={campaignGoal}
                onChange={(e) => setCampaignGoal(e.target.value)}
                placeholder="選填"
                className="min-h-[48px] w-full resize-y rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-muted-foreground">CTA 策略</label>
              <textarea
                value={ctaStrategy}
                onChange={(e) => setCtaStrategy(e.target.value)}
                placeholder="選填"
                className="min-h-[48px] w-full resize-y rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] text-muted-foreground">參考素材</label>
              <textarea
                value={referenceMaterials}
                onChange={(e) => setReferenceMaterials(e.target.value)}
                placeholder="連結或關鍵字，逗號分隔"
                className="min-h-[48px] w-full resize-y rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
              />
            </div>
          </div>
        </>
      )}

      {showManual && saveBlockers.length > 0 && (
        <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-100">
          還缺 {saveBlockers.join("、")}，補完後才能儲存策略。
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">
          {canSave ? "欄位已齊，可直接儲存。" : "長期經營項目需要頻率與內容比例才會寫回。"}
        </div>
        <Button
          size="sm"
          disabled={!canSave}
          onClick={async () => {
            if (!canSave) return;
            await onSave({
              audience: parsedAudience,
              tone: tone.trim(),
              coreMessage: coreMessage.trim(),
              platforms: parsedPlatforms,
              frequency: campaign.projectType === "long_term" ? frequency.trim() : undefined,
              contentMix: campaign.projectType === "long_term" ? parsedContentMix : undefined,
              campaignGoal: campaignGoal.trim(),
              ctaStrategy: ctaStrategy.trim(),
              referenceMaterials: parseCsv(referenceMaterials),
            });
          }}
        >
          {saving ? "儲存中..." : "儲存策略"}
        </Button>
      </div>
    </div>
  );
}

export function StyleManager({
  campaign,
  styles,
  onSaveStyle,
  onError,
  saving,
  onOpenCopilot,
}: {
  campaign: Campaign;
  styles: MarketingStyleBuckets;
  onSaveStyle: (input: {
    id?: string;
    title: string;
    level: MarketingStyle["level"];
    content: string;
    platform?: string;
  }) => Promise<void>;
  onError: (message: string) => void;
  saving: boolean;
  onOpenCopilot?: (config: FieldDiscussionConfig) => void;
}) {
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState<MarketingStyle["level"]>("project");
  const [platform, setPlatform] = useState("threads");
  const [content, setContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [previewTopic, setPreviewTopic] = useState(campaign.contentPlan?.[0]?.days?.[0]?.topic || campaign.posts[0]?.title || "範例主題");
  const [previewOutput, setPreviewOutput] = useState("");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const allStyles = [...styles.product, ...styles.platform, ...styles.project];
  const previewStyles = useMemo(() => {
    const nextStyles: MarketingStyleBuckets = {
      product: [...styles.product],
      platform: [...styles.platform],
      project: [...styles.project],
    };
    const trimmedTitle = title.trim();
    const trimmedContent = content.trim();
    if (trimmedTitle.length < 2 || trimmedContent.length < 10) {
      return nextStyles;
    }
    const draftStyle: MarketingStyle = {
      id: editingId || "__draft__",
      title: trimmedTitle,
      level,
      platform: level === "platform" ? platform.trim() || "threads" : null,
      projectId: level === "project" ? campaign.id : null,
      content: trimmedContent,
    };
    const bucket = nextStyles[level];
    const existingIndex = bucket.findIndex((style) => style.id === draftStyle.id);
    if (existingIndex >= 0) {
      bucket[existingIndex] = draftStyle;
    } else {
      bucket.unshift(draftStyle);
    }
    return nextStyles;
  }, [campaign.id, content, editingId, level, platform, styles.platform, styles.product, styles.project, title]);

  const beginEdit = (style: MarketingStyle) => {
    setEditingId(style.id);
    setTitle(style.title);
    setLevel(style.level);
    setPlatform(style.platform || "threads");
    setContent(style.content);
  };

  const runPreview = async () => {
    setPreviewing(true);
    setPreviewError(null);
    setPreviewOutput("");
    const previewPrompt = stylePreviewPrompt({
      styles: previewStyles,
      topic: previewTopic.trim() || "範例主題",
      platform: level === "platform" ? platform.trim() || undefined : campaign.strategy?.platforms?.[0],
      projectName: campaign.name,
    });
    let collected = "";
    try {
      await streamCoworkChat({
        baseUrl: getDefaultHelperBaseUrl(),
        token: getDefaultHelperToken() || "",
        mode: "start",
        conversationId: `marketing-style-preview-${campaign.id}`,
        prompt: previewPrompt,
        model: getDefaultHelperModel(),
        cwd: getDefaultHelperCwd(),
        maxTurns: 4,
        onEvent: (event: CoworkStreamEvent) => {
          if (event.type === "message") {
            const parsed = parseCoworkStreamLine(event.line);
            if (parsed.delta) {
              collected += parsed.delta;
              setPreviewOutput(collected);
              return;
            }
            if (!parsed.debug && event.line.trim()) {
              collected += `${collected ? "\n" : ""}${event.line.trim()}`;
              setPreviewOutput(collected);
            }
            return;
          }
          if (event.type === "error") {
            throw new Error(event.message);
          }
        },
      });
      if (!collected.trim()) {
        throw new Error("helper 沒有回傳預覽內容");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "文風預覽失敗";
      setPreviewError(msg);
      onError(msg);
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="rounded-xl border border-border/40 bg-card/70 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-foreground">文風管理</h3>
          <p className="mt-1 text-xs text-muted-foreground">三層 style 可直接 CRUD；預覽測試會直連本機 helper 產出測試文案。</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[0.6rem]">
            {campaign.projectType === "long_term" ? "長期項目" : "短期活動"}
          </Badge>
          <CopilotLaunchButton
            onClick={() =>
              onOpenCopilot?.({
                fieldId: "style",
                fieldLabel: "文風設定",
                currentPhase: "adapt",
                suggestedSkill: "/marketing-adapt",
                projectSummary: buildProjectSummary(campaign),
                conflictVersion: editingId ? allStyles.find((style) => style.id === editingId)?.updatedAt || null : null,
                conflictLabel: "文風",
                fieldValue: editingId
                  ? { title, level, platform, content }
                  : allStyles.map((style) => ({
                      title: style.title,
                      level: style.level,
                      platform: style.platform,
                      content: style.content,
                    })),
                relatedContext: "三層 style 組合：product + platform + project",
                onApply: async (payload) => {
                  if (payload.targetField !== "style" || !payload.value || typeof payload.value !== "object") {
                    throw new Error("AI 輸出的 style 結構不正確");
                  }
                  const record = payload.value as Record<string, unknown>;
                  const nextTitle = String(record.title || title || "AI 建議文風").trim();
                  const nextLevel = (record.level === "product" || record.level === "platform" || record.level === "project" ? record.level : level) as MarketingStyle["level"];
                  const nextPlatform = String(record.platform || platform || "threads").trim();
                  const nextContent = String(record.content || "").trim();
                  setTitle(nextTitle);
                  setLevel(nextLevel);
                  setPlatform(nextPlatform);
                  setContent(nextContent);
                  await onSaveStyle({
                    id: editingId || undefined,
                    title: nextTitle,
                    level: nextLevel,
                    content: nextContent,
                    platform: nextLevel === "platform" ? nextPlatform : undefined,
                  });
                },
              })
            }
          >
            帶進 AI
          </CopilotLaunchButton>
        </div>
      </div>

      <div className="space-y-2">
        {allStyles.length === 0 ? (
          <div className="rounded-md border border-border/30 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
            尚未建立文風。可先新增 project 級 style。
          </div>
        ) : (
          allStyles.map((style) => (
            <button
              key={style.id}
              type="button"
              onClick={() => beginEdit(style)}
              className="flex w-full items-start justify-between rounded-md border border-border/30 bg-background/60 px-3 py-2 text-left"
            >
              <div>
                <div className="text-xs font-medium text-foreground">{style.title}</div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  {style.level}
                  {style.platform ? ` / ${style.platform}` : ""}
                </div>
              </div>
              <div className="line-clamp-2 max-w-[60%] text-[11px] text-muted-foreground">{style.content}</div>
            </button>
          ))
        )}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="文風標題"
          className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
        />
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value as MarketingStyle["level"])}
          className="h-9 rounded-md border border-border/50 bg-background px-2 text-sm text-foreground outline-none ring-0 focus:border-primary/50"
        >
          <option value="project">Project 級</option>
          <option value="platform">Platform 級</option>
          <option value="product">Product 級</option>
        </select>
        {level === "platform" && (
          <input
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            placeholder="platform（例如 threads）"
            className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
          />
        )}
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="輸入 markdown 文風內容"
        className="mt-2 min-h-[96px] w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
      />
      <div className="mt-3 grid gap-2 rounded-lg border border-border/30 bg-background/60 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs font-medium text-foreground">預覽測試</div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              直接走本機 helper，不經後端；會套用目前三層 style 組合。
            </div>
          </div>
          <div className="text-[11px] text-muted-foreground">
            {composeStyleMarkdown(previewStyles, level === "platform" ? platform : undefined) ? "已載入 style 組合" : "尚無 style，會用中性語氣"}
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_120px]">
          <input
            value={previewTopic}
            onChange={(e) => setPreviewTopic(e.target.value)}
            placeholder="輸入範例主題"
            className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={previewing}
            onClick={() => {
              void runPreview();
            }}
          >
            {previewing ? "預覽中..." : "預覽測試"}
          </Button>
        </div>
        {previewError && (
          <div className="rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2 text-[11px] text-destructive">
            {previewError}
          </div>
        )}
        <div className="rounded-md border border-border/30 bg-card/60 px-3 py-2 text-xs text-muted-foreground">
          {previewOutput || "尚未生成預覽文案。"}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end">
        <Button
          size="sm"
          disabled={saving || title.trim().length < 2 || content.trim().length < 10}
          onClick={async () => {
            await onSaveStyle({
              id: editingId || undefined,
              title: title.trim(),
              level,
              content: content.trim(),
              platform: level === "platform" ? platform.trim() : undefined,
            });
            setEditingId(null);
            setTitle("");
            setLevel("project");
            setPlatform("threads");
            setContent("");
          }}
        >
          {saving ? "儲存中..." : editingId ? "更新文風" : "新增文風"}
        </Button>
      </div>
    </div>
  );
}

export function TopicStarter({
  campaign,
  onCreateTopic,
  onError,
  creatingTopic,
  onOpenCopilot,
}: {
  campaign: Campaign;
  onCreateTopic: (input: { topic: string; platform: string; brief: string }) => Promise<void>;
  onError: (message: string) => void;
  creatingTopic: boolean;
  onOpenCopilot?: (config: FieldDiscussionConfig) => void;
}) {
  const [topic, setTopic] = useState("");
  const [platform, setPlatform] = useState("Threads");
  const [brief, setBrief] = useState("");

  const canSubmit = topic.trim().length >= 2 && !creatingTopic;

  return (
    <div className="rounded-xl border border-border/40 bg-card/70 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-foreground">建立行銷主題</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            建立後會先進入主題規劃；下一步先做 <code>/marketing-intel</code>，也可直接跑 <code>/marketing-generate</code>。
          </p>
        </div>
        <CopilotLaunchButton
          onClick={() =>
            onOpenCopilot?.({
              fieldId: "topic",
              fieldLabel: "主題設定",
              currentPhase: "generate",
              suggestedSkill: "/marketing-generate",
              projectSummary: buildProjectSummary(campaign),
              fieldValue: { title: topic, brief, platform },
              relatedContext: campaign.strategy?.coreMessage,
              onApply: async (payload) => {
                if (payload.targetField !== "topic" || !payload.value || typeof payload.value !== "object") {
                  throw new Error("AI 輸出的 topic 結構不正確");
                }
                const record = payload.value as Record<string, unknown>;
                const nextTopic = String(record.title || "").trim();
                const nextBrief = String(record.brief || "").trim();
                const nextPlatform = String(record.platform || platform || "Threads").trim();
                setTopic(nextTopic);
                setBrief(nextBrief);
                setPlatform(nextPlatform);
                if (nextTopic.length < 2) {
                  throw new Error("AI 輸出的 topic title 不足");
                }
                await onCreateTopic({
                  topic: nextTopic,
                  brief: nextBrief,
                  platform: nextPlatform,
                });
              },
            })
          }
        >
          帶進 AI
        </CopilotLaunchButton>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_140px]">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="例如：跑步新手 7 天挑戰"
          className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
        />
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="h-9 rounded-md border border-border/50 bg-background px-2 text-sm text-foreground outline-none ring-0 focus:border-primary/50"
        >
          <option value="Threads">Threads</option>
          <option value="IG">IG</option>
          <option value="FB">FB</option>
          <option value="Blog">Blog</option>
        </select>
      </div>
      <textarea
        value={brief}
        onChange={(e) => setBrief(e.target.value)}
        placeholder="補充目標、角度或限制（選填）"
        className="mt-2 min-h-[72px] w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
      />
      <div className="mt-3 flex justify-end">
        <Button
          size="sm"
          disabled={!canSubmit}
          onClick={async () => {
            if (!canSubmit) return;
            await onCreateTopic({ topic: topic.trim(), platform, brief: brief.trim() });
            setTopic("");
            setBrief("");
          }}
        >
          建立主題
        </Button>
      </div>
    </div>
  );
}

export function CampaignDetail({
  campaign,
  onBack,
  onReview,
  reviewingPostId,
  onSaveContentPlan,
  savingPlan,
  onCreateTopic,
  creatingTopic,
  onSaveStrategy,
  onError,
  savingStrategy,
  styles,
  onSaveStyle,
  savingStyle,
  onOpenCopilot,
  copilotRail,
}: {
  campaign: Campaign;
  onBack: () => void;
  onReview: (postId: string, action: "approve" | "request_changes" | "reject") => void;
  reviewingPostId: string | null;
  onSaveContentPlan: (contentPlan: WeekPlan[]) => Promise<void>;
  savingPlan: boolean;
  onCreateTopic: (input: { topic: string; platform: string; brief: string }) => Promise<void>;
  creatingTopic: boolean;
  onSaveStrategy: (input: {
    audience: string[];
    tone: string;
    coreMessage: string;
    platforms: string[];
    frequency?: string;
    contentMix?: Record<string, number>;
    campaignGoal?: string;
    ctaStrategy?: string;
    referenceMaterials?: string[];
  }) => Promise<void>;
  onError: (message: string) => void;
  savingStrategy: boolean;
  styles: MarketingStyleBuckets;
  onSaveStyle: (input: {
    id?: string;
    title: string;
    level: MarketingStyle["level"];
    content: string;
    platform?: string;
  }) => Promise<void>;
  savingStyle: boolean;
  onOpenCopilot?: (config: FieldDiscussionConfig) => void;
  copilotRail?: ReactNode;
}) {
  const review = campaign.posts.filter((p) => requiresReview(p.status));
  const planned = campaign.posts.filter((p) => isPlannedStatus(p.status));
  const confirmed = campaign.posts.filter((p) => isConfirmedStatus(p.status));
  const scheduled = campaign.posts.filter((p) => p.status === "scheduled");
  const published = campaign.posts.filter((p) => p.status === "published");
  const currentStage = deriveProjectStage(campaign);
  const primaryCta = primaryCtaForProject(campaign);
  const phaseLabels = [
    { key: "strategy", label: "策略" },
    { key: "schedule", label: "排程" },
    { key: "intel", label: "情報" },
    { key: "generate", label: "生成" },
    { key: "review", label: "確認" },
    { key: "publish", label: "發佈" },
  ] as const;
  const unlockedTopicStarter = Boolean(campaign.strategy?.documentId);
  const anyFailedPost = campaign.posts.find((post) => post.status === "failed");

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/60 bg-card/80 text-muted-foreground hover:bg-card hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-foreground">{campaign.name}</h2>
          <p className="text-xs text-muted-foreground">{campaign.description}</p>
        </div>
      </div>

      <div className="rounded-xl border border-border/40 bg-card/70 p-4">
        <div className="flex flex-wrap items-center gap-2">
          {phaseLabels.map((phase, index) => {
            const isCurrent = phase.key === currentStage;
            const isDone = index < phaseLabels.findIndex((item) => item.key === currentStage);
            return (
              <div
                key={phase.key}
                className={`rounded-full border px-2.5 py-1 text-[11px] ${
                  isCurrent
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : isDone
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                      : "border-border/40 bg-background/60 text-muted-foreground"
                }`}
              >
                {phase.label}
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-3">
          <div>
            <div className="text-sm font-medium text-foreground">{primaryCta.label}</div>
            <div className="mt-1 text-xs text-muted-foreground">{primaryCta.hint}</div>
          </div>
          <Badge variant="outline" className="text-[0.65rem]">
            目前階段：{phaseLabels.find((item) => item.key === currentStage)?.label}
          </Badge>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full border border-border/30 bg-background/60 px-2.5 py-1">按「帶進 AI」開始</span>
          <span className="rounded-full border border-border/30 bg-background/60 px-2.5 py-1">集中在同一個 AI 工作區討論</span>
          <span className="rounded-full border border-border/30 bg-background/60 px-2.5 py-1">有 structured result 才套用</span>
        </div>
      </div>

      {campaign.blockReason && (
        <div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          <div>
            <div className="text-sm font-medium text-foreground">{campaign.blockReason}</div>
            <p className="mt-1 text-xs text-muted-foreground">解決後 AI 會自動開始準備內容。</p>
          </div>
        </div>
      )}

      {anyFailedPost && (
        <div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          <div>
            <div className="text-sm font-medium text-foreground">AI 流程中斷</div>
            <p className="mt-1 text-xs text-muted-foreground">
              {anyFailedPost.aiReason || "請先檢查 helper / 重新執行上一階段，再繼續後續流程。"}
            </p>
          </div>
        </div>
      )}

      <div data-testid="campaign-detail-layout" className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,420px)] xl:items-start">
        <aside className="order-1 space-y-5 xl:sticky xl:top-24 xl:order-2">{copilotRail}</aside>
        <div className="order-2 space-y-5 xl:order-1">
          <StrategyPlanner
            campaign={campaign}
            strategy={campaign.strategy}
            onSave={onSaveStrategy}
            onError={onError}
            saving={savingStrategy}
            onOpenCopilot={onOpenCopilot}
          />
          <StyleManager
            campaign={campaign}
            styles={styles}
            onSaveStyle={onSaveStyle}
            onError={onError}
            saving={savingStyle}
            onOpenCopilot={onOpenCopilot}
          />
          {campaign.strategy && (
            <StrategyAndPlan
              campaign={campaign}
              strategy={campaign.strategy}
              contentPlan={campaign.contentPlan}
              posts={campaign.posts}
              onSavePlan={onSaveContentPlan}
              savingPlan={savingPlan}
              onError={onError}
              onOpenCopilot={onOpenCopilot}
            />
          )}
          {unlockedTopicStarter ? (
            <TopicStarter
              campaign={campaign}
              onCreateTopic={onCreateTopic}
              onError={onError}
              creatingTopic={creatingTopic}
              onOpenCopilot={onOpenCopilot}
            />
          ) : (
            <div className="rounded-xl border border-border/40 bg-card/70 p-4 text-xs text-muted-foreground">
              先完成策略設定，再建立主題與排程；不要同時跳兩步。
            </div>
          )}

          {review.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-amber-400">待你確認</h3>
              {review.map((post) => (
                <PostCard
                  key={post.id}
                  campaignId={campaign.id}
                  post={post}
                  onReview={onReview}
                  isReviewing={reviewingPostId === post.id}
                  onError={onError}
                  onOpenCopilot={onOpenCopilot}
                />
              ))}
            </section>
          )}

          {planned.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-primary">規劃中</h3>
              {planned.map((post) => (
                <PostCard
                  key={post.id}
                  campaignId={campaign.id}
                  post={post}
                  onReview={onReview}
                  isReviewing={reviewingPostId === post.id}
                  onError={onError}
                  onOpenCopilot={onOpenCopilot}
                />
              ))}
            </section>
          )}

          {confirmed.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-primary">已確認</h3>
              {confirmed.map((post) => (
                <PostCard
                  key={post.id}
                  campaignId={campaign.id}
                  post={post}
                  onReview={onReview}
                  isReviewing={reviewingPostId === post.id}
                  onError={onError}
                  onOpenCopilot={onOpenCopilot}
                />
              ))}
            </section>
          )}

          {scheduled.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-chart-2">已排程</h3>
              {scheduled.map((post) => (
                <PostCard
                  key={post.id}
                  campaignId={campaign.id}
                  post={post}
                  onReview={onReview}
                  isReviewing={reviewingPostId === post.id}
                  onError={onError}
                  onOpenCopilot={onOpenCopilot}
                />
              ))}
            </section>
          )}

          {published.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">已發佈</h3>
              {published.map((post) => (
                <PostCard
                  key={post.id}
                  campaignId={campaign.id}
                  post={post}
                  onReview={onReview}
                  isReviewing={reviewingPostId === post.id}
                  onError={onError}
                  onOpenCopilot={onOpenCopilot}
                />
              ))}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MarketingPage() {
  const {
    activeFieldContext,
    activePromptContext,
    campaignGroups,
    copilotOpen,
    creatingCampaign,
    creatingTopic,
    error,
    handleCreateCampaign,
    handleCreateTopic,
    handleOpenFieldCopilot,
    handleOpenPromptCopilot,
    handleReview,
    handleSaveContentPlan,
    handleSaveStrategy,
    handleSaveStyle,
    loading,
    productOptions,
    projectStyles,
    reviewingPostId,
    savingPlan,
    savingStrategy,
    savingStyle,
    selectedCampaign,
    selectedFromList,
    selectedId,
    setCopilotOpen,
    setError,
    setSelectedId,
    user,
  } = useMarketingWorkspace();

  return (
      <div className="min-h-screen bg-background text-foreground">
        <main id="main-content" className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h1 className="text-[1.65rem] font-semibold tracking-[-0.03em] text-foreground">行銷主控台</h1>
              <p className="mt-1 text-sm font-medium text-[#bcd3e7]">Paceriz</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-card/70 p-1.5 shadow-[0_14px_34px_rgba(0,0,0,0.14)]">
              <PromptManagerSheet
                user={user ? { getIdToken: () => user.getIdToken() } : null}
                onError={setError}
                onOpenPromptCopilot={handleOpenPromptCopilot}
              />
              <FlowGuideSheet campaignId={selectedId} />
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          {loading ? (
            <div className="rounded-xl border border-border/40 bg-card/50 p-6 text-sm text-muted-foreground">載入中...</div>
          ) : selectedId ? (
            <CampaignDetail
              campaign={selectedCampaign || selectedFromList || {
                id: selectedId,
                name: "載入中...",
                description: "",
                status: "active",
                projectType: "long_term",
                thisWeek: { posts: 0, approved: 0, published: 0 },
                stats: { followers: "—", postsThisMonth: 0, avgEngagement: "—" },
                trend: { followers: "—", engagement: "—" },
                posts: [],
              }}
              onBack={() => setSelectedId(null)}
              onReview={handleReview}
              reviewingPostId={reviewingPostId}
              onSaveContentPlan={handleSaveContentPlan}
              savingPlan={savingPlan}
              onCreateTopic={handleCreateTopic}
              creatingTopic={creatingTopic}
              onSaveStrategy={handleSaveStrategy}
              onError={setError}
              savingStrategy={savingStrategy}
              styles={projectStyles}
              onSaveStyle={handleSaveStyle}
              savingStyle={savingStyle}
              onOpenCopilot={handleOpenFieldCopilot}
              copilotRail={
                <CoworkChatSheet
                  campaignId={selectedId}
                  onError={(message) => setError(message)}
                  open={copilotOpen}
                  onOpenChange={setCopilotOpen}
                  hideTrigger
                  inlineOnly
                  fieldContext={activeFieldContext}
                  promptContext={activePromptContext}
                />
              }
            />
          ) : (
            <div className="space-y-4">
              <CampaignStarter
                productOptions={productOptions}
                onCreateCampaign={handleCreateCampaign}
                creatingCampaign={creatingCampaign}
              />
              <CampaignList groups={campaignGroups} onSelect={setSelectedId} />
            </div>
          )}
        </main>
      </div>
  );
}
