"use client";

import { AppNav } from "@/components/AppNav";
import { AuthGuard } from "@/components/AuthGuard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  REDACTION_RULES_VERSION,
  serializeSanitizedContextValue,
} from "@/config/ai-redaction-rules";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
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
import {
  MarketingProject,
  MarketingProjectGroup,
  MarketingStyle,
  MarketingStyleBuckets,
  MarketingPrompt,
  Post,
  Strategy,
  WeekPlan,
  createMarketingProject,
  createMarketingStyle,
  createMarketingTopic,
  getMarketingProjectDetail,
  getMarketingProjectGroups,
  getMarketingProjectStyles,
  getMarketingPrompts,
  publishMarketingPrompt,
  reviewMarketingPost,
  updateMarketingProjectStrategy,
  updateMarketingPromptDraft,
  updateMarketingStyle,
} from "@/lib/marketing-api";
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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Campaign = MarketingProject;
type CampaignGroup = MarketingProjectGroup;
type DiscussionFieldId = "strategy" | "topic" | "style" | "schedule" | "review";
type DiscussionPhase = "strategy" | "schedule" | "intel" | "generate" | "adapt" | "publish";
type ChatStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "awaiting-local-approval"
  | "apply-ready"
  | "applying"
  | "error";

interface ContextPack {
  field_id: DiscussionFieldId;
  field_value: string | null;
  project_summary: string;
  current_phase: DiscussionPhase;
  suggested_skill: string;
  related_context?: string;
}

interface StructuredApplyPayload {
  targetField: DiscussionFieldId;
  value: unknown;
}

interface FieldDiscussionConfig {
  fieldId: DiscussionFieldId;
  fieldLabel: string;
  currentPhase: DiscussionPhase;
  suggestedSkill: string;
  projectSummary: string;
  fieldValue: unknown;
  relatedContext?: string;
  launcherLabel?: string;
  conflictVersion?: string | null;
  conflictLabel?: string;
  onApply?: (payload: StructuredApplyPayload) => void | Promise<void>;
}

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

function formatCsv(values: string[] | undefined): string {
  return (values || []).join(", ");
}

function parseCsv(value: string): string[] {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatContentMix(contentMix: Record<string, number> | undefined): string {
  if (!contentMix || Object.keys(contentMix).length === 0) return "";
  return Object.entries(contentMix)
    .map(([key, value]) => `${key}:${value}`)
    .join(", ");
}

function parseContentMix(value: string): Record<string, number> {
  const trimmed = value.trim();
  if (!trimmed) return {};
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    const result: Record<string, number> = {};
    for (const [key, raw] of Object.entries(parsed)) {
      const num = Number(raw);
      if (key.trim() && Number.isFinite(num)) result[key.trim()] = num;
    }
    if (Object.keys(result).length > 0) return result;
  } catch {}

  const result: Record<string, number> = {};
  for (const chunk of trimmed.split(/[,，\n]/)) {
    const [rawKey, rawValue] = chunk.split(/[:：]/);
    const key = rawKey?.trim();
    const num = Number(rawValue?.trim());
    if (key && Number.isFinite(num)) result[key] = num;
  }
  return result;
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function buildProjectSummary(campaign: Campaign): string {
  const parts = [
    campaign.name,
    campaign.projectType === "long_term" ? "長期經營" : "短期活動",
    campaign.description,
  ].filter(Boolean);
  if (campaign.strategy?.coreMessage) {
    parts.push(`核心訊息：${campaign.strategy.coreMessage}`);
  }
  if (campaign.strategy?.platforms?.length) {
    parts.push(`平台：${campaign.strategy.platforms.join(" / ")}`);
  }
  return truncateText(parts.join(" / "), 500);
}

function buildContextPack(input: {
  fieldId: DiscussionFieldId;
  currentPhase: DiscussionPhase;
  suggestedSkill: string;
  projectSummary: string;
  fieldValue: unknown;
  relatedContext?: string;
}): ContextPack {
  const sanitizedFieldValue = serializeSanitizedContextValue(input.fieldValue);
  const sanitizedProjectSummary = truncateText(input.projectSummary.trim(), 500);
  const sanitizedRelatedContext = input.relatedContext
    ? truncateText(String(serializeSanitizedContextValue(input.relatedContext) || ""), 1000)
    : undefined;
  let fieldValue = sanitizedFieldValue ? truncateText(sanitizedFieldValue, 1200) : null;
  let relatedContext = sanitizedRelatedContext;
  let totalLength =
    (fieldValue?.length || 0) +
    sanitizedProjectSummary.length +
    (relatedContext?.length || 0);
  if (totalLength > 2000 && relatedContext) {
    relatedContext = truncateText(relatedContext, Math.max(0, relatedContext.length - (totalLength - 2000)));
    totalLength =
      (fieldValue?.length || 0) +
      sanitizedProjectSummary.length +
      (relatedContext?.length || 0);
  }
  if (totalLength > 2000 && fieldValue) {
    fieldValue = truncateText(fieldValue, Math.max(0, fieldValue.length - (totalLength - 2000)));
  }
  return {
    field_id: input.fieldId,
    field_value: fieldValue,
    project_summary: sanitizedProjectSummary,
    current_phase: input.currentPhase,
    suggested_skill: input.suggestedSkill,
    related_context: relatedContext,
  };
}

function buildDiscussionPrompt(field: FieldDiscussionConfig, userPrompt: string): string {
  const contextPack = buildContextPack({
    fieldId: field.fieldId,
    currentPhase: field.currentPhase,
    suggestedSkill: field.suggestedSkill,
    projectSummary: field.projectSummary,
    fieldValue: field.fieldValue,
    relatedContext: field.relatedContext,
  });
  const schemaExamples: Record<DiscussionFieldId, string> = {
    strategy: '{"target_field":"strategy","value":{"audience":["跑步新手"],"tone":"專業但親切","core_message":"先建立習慣再談進階裝備","platforms":["Threads","Blog"]}}',
    topic: '{"target_field":"topic","value":{"title":"跑步新手 7 天挑戰","brief":"聚焦新手容易卡關的三個理由","platform":"Threads"}}',
    style: '{"target_field":"style","value":{"title":"Threads 親切教練風","content":"# 語氣\\n- 親切\\n- 直接\\n","platform":"Threads"}}',
    schedule: '{"target_field":"schedule","value":[{"date":"2026-04-20","platform":"Threads","topic":"跑步新手暖身","reason":"銜接前一篇 FAQ"}]}',
    review: '{"target_field":"review","value":{"summary":"指出 CTA 過弱","suggestion":"把 CTA 改成具體下載動作"}}',
  };
  const baseInstruction = contextPack.field_value
    ? `以下是目前的${field.fieldLabel}，請先給修改建議，再整理成結構化結果。`
    : `請幫我設定這個項目的${field.fieldLabel}，先用白話說明你的建議，再整理成結構化結果。`;
  const userLine = userPrompt.trim() ? `使用者補充：${userPrompt.trim()}` : "使用者補充：若資訊不足，先提出最多 3 個澄清問題，再給暫定方案。";
  return [
    "你是 ZenOS 行銷協作助手。",
    baseInstruction,
    "回覆格式：先用白話分析，再輸出一段 ```json```。",
    "JSON 必須符合回寫契約：包含 target_field 與 value。",
    `請使用這個 target_field：${field.fieldId}`,
    `最小範例：${schemaExamples[field.fieldId]}`,
    `建議 skill：${field.suggestedSkill}`,
    `context_pack=${JSON.stringify(contextPack, null, 2)}`,
    userLine,
  ].join("\n");
}

function validateStructuredValue(targetField: DiscussionFieldId, value: unknown): string[] {
  if (value == null) return ["value"];
  if (targetField === "strategy") {
    const record = value as Record<string, unknown>;
    return ["audience", "tone", "core_message", "platforms"].filter((key) => !(key in record) && !(key.replace("_", "") in record));
  }
  if (targetField === "topic") {
    const record = value as Record<string, unknown>;
    return ["title", "brief"].filter((key) => !(key in record));
  }
  if (targetField === "style") {
    const record = value as Record<string, unknown>;
    return ["content"].filter((key) => !(key in record));
  }
  if (targetField === "schedule") {
    if (!Array.isArray(value) || value.length === 0) return ["date", "platform", "topic", "reason"];
    return ["date", "platform", "topic", "reason"].filter((key) => !(key in (value[0] as Record<string, unknown>)));
  }
  return [];
}

function parseStructuredApplyPayload(raw: string, expectedFieldId?: DiscussionFieldId): { payload: StructuredApplyPayload | null; missingKeys: string[] } {
  const candidates: string[] = [];
  const trimmed = raw.trim();
  if (trimmed) candidates.push(trimmed);
  const fenced = raw.match(/```json\s*([\s\S]*?)```/i) || raw.match(/```\s*([\s\S]*?)```/i);
  if (fenced?.[1]) candidates.push(fenced[1].trim());
  const firstBrace = raw.indexOf("{");
  const lastBrace = raw.lastIndexOf("}");
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    candidates.push(raw.slice(firstBrace, lastBrace + 1).trim());
  }
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate) as Record<string, unknown>;
      let targetField = parsed.target_field as DiscussionFieldId | undefined;
      let value = parsed.value;
      if (!targetField && expectedFieldId) {
        targetField = expectedFieldId;
        value = parsed;
      }
      if (!targetField || !["strategy", "topic", "style", "schedule", "review"].includes(targetField)) continue;
      const missingKeys = validateStructuredValue(targetField, value);
      return {
        payload: missingKeys.length === 0 ? { targetField, value } : null,
        missingKeys,
      };
    } catch {
      continue;
    }
  }
  return { payload: null, missingKeys: [] };
}

function statusConfig(status: Post["status"]) {
  switch (status) {
    case "topic_planned":
      return { label: "主題已規劃", class: "border-primary/30 bg-primary/10 text-primary" };
    case "intel_ready":
      return { label: "情報已就緒", class: "border-primary/30 bg-primary/10 text-primary" };
    case "draft_generated":
      return { label: "主文案待確認", class: "border-amber-400/30 bg-amber-400/10 text-amber-400" };
    case "draft_confirmed":
      return { label: "主文案已確認", class: "border-primary/30 bg-primary/10 text-primary" };
    case "platform_adapted":
      return { label: "平台版本待確認", class: "border-amber-400/30 bg-amber-400/10 text-amber-400" };
    case "platform_confirmed":
      return { label: "平台版本已確認", class: "border-primary/30 bg-primary/10 text-primary" };
    case "scheduled":
      return { label: "已排程", class: "border-chart-2/30 bg-chart-2/10 text-chart-2" };
    case "published":
      return { label: "已發佈", class: "border-border/40 bg-muted/20 text-muted-foreground" };
    case "failed":
      return { label: "流程失敗", class: "border-destructive/30 bg-destructive/10 text-destructive" };
  }
}

function requiresReview(status: Post["status"]) {
  return status === "draft_generated" || status === "platform_adapted";
}

function isPlannedStatus(status: Post["status"]) {
  return status === "topic_planned" || status === "intel_ready";
}

function isConfirmedStatus(status: Post["status"]) {
  return status === "draft_confirmed" || status === "platform_confirmed";
}

function campaignStatusConfig(status: Campaign["status"]) {
  switch (status) {
    case "active":
      return { dot: "bg-primary", badge: "border-primary/30 bg-primary/10 text-primary", label: "進行中" };
    case "blocked":
      return { dot: "bg-destructive", badge: "border-destructive/30 bg-destructive/10 text-destructive", label: "暫停" };
    case "completed":
      return { dot: "bg-muted-foreground", badge: "border-border/40 bg-muted/20 text-muted-foreground", label: "已結束" };
  }
}

function MetricPill({ icon: Icon, value }: { icon: typeof Heart; value: number | undefined }) {
  if (!value) return null;
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Icon className="h-3 w-3" />
      {value}
    </span>
  );
}

function CampaignList({ groups, onSelect }: { groups: CampaignGroup[]; onSelect: (id: string) => void }) {
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
              <Badge variant="outline" className="text-[0.65rem]">
                {group.product.name}
              </Badge>
              <span className="text-[11px] text-muted-foreground">{group.projects.length} 個項目</span>
            </div>
            <div className="space-y-3">
              {group.projects.map((campaign) => {
                const sc = campaignStatusConfig(campaign.status);
                const reviewCount = campaign.posts.filter((p) => requiresReview(p.status)).length;
                return (
                  <div
                    key={campaign.id}
                    className="group cursor-pointer rounded-xl border border-border/50 bg-card/70 transition-all hover:border-border hover:bg-card"
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
                          <p className="ml-4 mt-0.5 text-xs text-muted-foreground">{campaign.description}</p>
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
                            <div className="text-[0.55rem] text-muted-foreground">追蹤者</div>
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-foreground">{campaign.stats.avgEngagement}</div>
                            <div className="text-[0.55rem] text-muted-foreground">平均互動率</div>
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-foreground">{campaign.stats.postsThisMonth}</div>
                            <div className="text-[0.55rem] text-muted-foreground">本月發文</div>
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

function CampaignStarter({
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
    <div className="rounded-xl border border-border/40 bg-card/70 p-4">
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

function StrategyAndPlan({ strategy, contentPlan }: { strategy: Strategy; contentPlan?: WeekPlan[] }) {
  const [showStrategy, setShowStrategy] = useState(false);

  const planStatusDot = {
    published: "bg-muted-foreground/40",
    confirmed: "bg-primary",
    suggested: "bg-amber-400",
  } as const;

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
          <div className="flex items-center gap-3 border-b border-border/30 px-4 py-3">
            <Calendar className="h-4 w-4 shrink-0 text-primary" />
            <span className="text-sm font-medium text-foreground">內容排程</span>
          </div>
          <div className="divide-y divide-border/20">
            {contentPlan.map((week) => (
              <div key={week.weekLabel} className="px-4 py-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className={`text-xs font-medium ${week.isCurrent ? "text-foreground" : "text-muted-foreground"}`}>{week.weekLabel}</span>
                </div>
                <div className="space-y-1.5">
                  {week.days.map((day, i) => (
                    <div key={`${day.day}-${day.platform}-${i}`} className="flex items-center gap-3 text-xs">
                      <span className="w-8 shrink-0 text-muted-foreground">{day.day}</span>
                      <span className={`w-7 shrink-0 rounded px-1 py-0.5 text-center text-[0.55rem] font-medium ${platformColor[day.platform] || "bg-muted/20 text-muted-foreground"}`}>
                        {platformIcon[day.platform] || day.platform}
                      </span>
                      <span className="flex-1 text-foreground/85">{day.topic}</span>
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${planStatusDot[day.status]}`} />
                    </div>
                  ))}
                </div>
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
  post,
  onReview,
  isReviewing,
}: {
  post: Post;
  onReview: (postId: string, action: "approve" | "request_changes" | "reject") => void;
  isReviewing: boolean;
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
            <div className="flex items-center gap-2">
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
          )}

          {isPlanned && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Zap className="h-3.5 w-3.5 text-primary" />
              {post.status === "topic_planned"
                ? <>下一步先執行 <code>/marketing-intel</code> 補齊情報，再進入文案生成。</>
                : <>下一步到 Claude cowork 執行 <code>/marketing-generate</code> 產生正式文案。</>}
            </div>
          )}

          {isConfirmed && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Zap className="h-3.5 w-3.5 text-primary" />
                {isMasterConfirmed
                  ? "主文案已確認，下一步直接複製平台適配指令。"
                  : "平台版本已確認，下一步直接複製發佈指令。"}
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

function FlowGuideSheet({ campaignId }: { campaignId: string | null }) {
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

function PromptManagerSheet({
  user,
  onError,
}: {
  user: { getIdToken: () => Promise<string> } | null;
  onError: (message: string) => void;
}) {
  const [prompts, setPrompts] = useState<MarketingPrompt[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string>("marketing-generate");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);

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
    <Sheet>
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
            <div className="rounded-lg border border-border/40 bg-card/60 p-3 text-xs text-muted-foreground">載入中...</div>
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

function parseCoworkStreamLine(line: string): { delta: string; debug: string } {
  const raw = line.trim();
  if (!raw) return { delta: "", debug: "" };
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const type = typeof parsed.type === "string" ? parsed.type : "";
    const candidates: unknown[] = [
      (parsed.delta as Record<string, unknown> | undefined)?.text,
      (parsed.content_block_delta as Record<string, unknown> | undefined)?.text,
      parsed.text,
      (parsed.content_block as Record<string, unknown> | undefined)?.text,
      (parsed.message as Record<string, unknown> | undefined)?.text,
    ];
    const messageObj = parsed.message as Record<string, unknown> | undefined;
    const messageContent = Array.isArray(messageObj?.content) ? messageObj?.content : null;
    if (messageContent && messageContent.length > 0) {
      const first = messageContent[0] as Record<string, unknown>;
      candidates.push(first?.text);
      const nested = first?.content as Record<string, unknown> | undefined;
      candidates.push(nested?.text);
    }
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim().length > 0) {
        return { delta: candidate, debug: "" };
      }
    }
    if (type) {
      if (type.includes("delta")) return { delta: "", debug: "" };
      const blockType =
        (parsed.content_block as Record<string, unknown> | undefined)?.type ||
        (parsed.delta as Record<string, unknown> | undefined)?.type ||
        "";
      const suffix = typeof blockType === "string" && blockType ? ` (${blockType})` : "";
      return { delta: "", debug: `事件：${type}${suffix}` };
    }
    return { delta: "", debug: "" };
  } catch {
    return { delta: "", debug: raw };
  }
}

function CoworkChatSheet({
  campaignId,
  onUseOutput,
  onError,
  launcherLabel = "AI 討論（Beta）",
  fieldContext,
}: {
  campaignId: string | null;
  onUseOutput?: (output: string) => void;
  onError: (message: string) => void;
  launcherLabel?: string;
  fieldContext?: FieldDiscussionConfig;
}) {
  const generateHelperToken = () =>
    `mk-${Math.random().toString(36).slice(2, 8)}${Math.random().toString(36).slice(2, 8)}`;
  const effectiveCampaignId = campaignId || "global";
  const conversationScope = fieldContext?.fieldId || "general";
  const startedStorageKey = `zenos.marketing.cowork.started.${effectiveCampaignId}.${conversationScope}`;
  const allowedOrigins = "https://zenos-naruvia.web.app";
  const helperInstallCommand = "curl -fsSL https://zenos-naruvia.web.app/installers/install-claude-code-helper-macos.sh | bash";
  const [helperBaseUrl, setHelperBaseUrlState] = useState(getDefaultHelperBaseUrl());
  const [helperToken, setHelperTokenState] = useState(getDefaultHelperToken() || generateHelperToken());
  const [helperCwd, setHelperCwdState] = useState(getDefaultHelperCwd());
  const [helperModel, setHelperModelState] = useState(getDefaultHelperModel());
  const helperSecureStartCommand = `SAFE_WORKSPACE=$HOME/.zenos/claude-code-helper/workspace LOCAL_HELPER_TOKEN=${helperToken || "<your_token>"} ALLOWED_ORIGINS=${allowedOrigins} ~/.zenos/claude-code-helper/start-secure.sh`;
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [healthText, setHealthText] = useState("未檢查");
  const [running, setRunning] = useState(false);
  const [chatStatus, setChatStatus] = useState<ChatStatus>("idle");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [streamingOutput, setStreamingOutput] = useState("");
  const [capability, setCapability] = useState<CoworkCapabilityCheck | null>(null);
  const [applyPayload, setApplyPayload] = useState<StructuredApplyPayload | null>(null);
  const [missingApplyKeys, setMissingApplyKeys] = useState<string[]>([]);
  const chatViewportRef = useRef<HTMLDivElement | null>(null);
  const [hasStartedConversation, setHasStartedConversation] = useState(false);
  const [copiedInstall, setCopiedInstall] = useState(false);
  const [copiedSecureStart, setCopiedSecureStart] = useState(false);
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const baselineConflictVersionRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const started = window.localStorage.getItem(startedStorageKey) === "1";
    setHasStartedConversation(started);
  }, [startedStorageKey]);

  useEffect(() => {
    const el = chatViewportRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [logLines, streamingOutput]);

  useEffect(() => {
    if (!open) return;
    baselineConflictVersionRef.current = fieldContext?.conflictVersion || null;
  }, [open, fieldContext?.conflictVersion]);

  useEffect(() => {
    setLogLines([]);
    setStreamingOutput("");
    setApplyPayload(null);
    setMissingApplyKeys([]);
    setChatStatus("idle");
    setRequestId(null);
  }, [effectiveCampaignId, conversationScope]);

  const conversationId = `marketing-${effectiveCampaignId}-${conversationScope}`;
  const contextPack = useMemo(
    () =>
      fieldContext
        ? buildContextPack({
            fieldId: fieldContext.fieldId,
            currentPhase: fieldContext.currentPhase,
            suggestedSkill: fieldContext.suggestedSkill,
            projectSummary: fieldContext.projectSummary,
            fieldValue: fieldContext.fieldValue,
            relatedContext: fieldContext.relatedContext,
          })
        : null,
    [fieldContext]
  );
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
    if (typeof window !== "undefined") {
      if (started) {
        window.localStorage.setItem(startedStorageKey, "1");
      } else {
        window.localStorage.removeItem(startedStorageKey);
      }
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
    setCapability(health.capability || null);
    setHealthText(health.ok ? "可連線" : `不可用：${health.message || health.status}`);
    setCheckingHealth(false);
  };

  const sendMessage = async () => {
    const userPrompt = prompt.trim();
    if (running || (!userPrompt && !fieldContext)) return;
    const effectivePrompt = fieldContext ? buildDiscussionPrompt(fieldContext, userPrompt) : userPrompt;
    persistHelperSettings();
    setPrompt("");
    setRunning(true);
    setChatStatus("loading");
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
        maxTurns: 8,
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
            setChatStatus("awaiting-local-approval");
            setLogLines((prev) => [...prev, `系統：等待本機 terminal 確認 ${event.request.toolName}（${event.request.timeoutSeconds} 秒）`]);
            return;
          }
          if (event.type === "permission_result") {
            setLogLines((prev) => [...prev, `系統：${event.result.toolName} ${event.result.approved ? "已核准" : `已拒絕（${event.result.reason || "unknown"}）`}`]);
            setChatStatus("streaming");
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
            setChatStatus("streaming");
            const parsed = parseCoworkStreamLine(event.line);
            if (parsed.delta) {
              collected += parsed.delta;
              setStreamingOutput(collected);
              return;
            }
            if (parsed.debug) {
              setLogLines((prev) => [...prev, `系統：${parsed.debug}`]);
            }
            return;
          }
          if (event.type === "done") {
            if (typeof event.code === "number") {
              exitCode = event.code;
            }
            if (collected.trim()) {
              setLogLines((prev) => [...prev, `Claude：${collected.trim()}`]);
              const { payload, missingKeys } = parseStructuredApplyPayload(collected.trim(), fieldContext?.fieldId);
              if (payload && fieldContext?.onApply) {
                setApplyPayload(payload);
                setChatStatus("apply-ready");
              } else {
                setChatStatus("idle");
              }
              if (missingKeys.length > 0) {
                setMissingApplyKeys(missingKeys);
                setLogLines((prev) => [...prev, `系統：結構化結果缺少鍵：${missingKeys.join(", ")}`]);
              }
              if (!payload) {
                onUseOutput?.(collected.trim());
              }
            } else if (chatStatus !== "error") {
              setChatStatus("idle");
            }
          }
          if (event.type === "error") {
            setChatStatus("error");
            setLogLines((prev) => [...prev, `系統：${event.message}`]);
          }
        },
      });

      if (exitCode !== null && exitCode !== 0) {
        throw new Error(stderrCombined || `Claude Code CLI exited with code ${exitCode}`);
      }
    };

    try {
      if (hasStartedConversation) {
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
       setChatStatus("error");
      setLogLines((prev) => [...prev, `系統：${msg}`]);
      onError(msg);
    } finally {
      setRunning(false);
      setStreamingOutput("");
      setRequestId(null);
    }
  };

  const handleCancel = async () => {
    if (!requestId || !running) return;
    try {
      await cancelCoworkRequest({
        baseUrl: helperBaseUrl,
        token: helperToken,
        requestId,
      });
      setLogLines((prev) => [...prev, "系統：已送出取消請求"]);
      setChatStatus("idle");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "取消失敗";
      setLogLines((prev) => [...prev, `系統：${msg}`]);
      setChatStatus("error");
      onError(msg);
    }
  };

  const handleApply = async () => {
    if (!applyPayload || !fieldContext?.onApply) return;
    try {
      const baselineVersion = baselineConflictVersionRef.current;
      const currentVersion = fieldContext.conflictVersion || null;
      if (baselineVersion && currentVersion && baselineVersion !== currentVersion) {
        const shouldOverwrite = window.confirm(
          `${fieldContext.conflictLabel || fieldContext.fieldLabel} 在你對話期間已被其他來源更新。按「確定」覆蓋，按「取消」放棄套用。`
        );
        if (!shouldOverwrite) {
          setLogLines((prev) => [...prev, `系統：已放棄套用，因為 ${fieldContext.fieldLabel} 發生衝突。`]);
          setChatStatus("idle");
          setApplyPayload(null);
          return;
        }
      }
      setChatStatus("applying");
      await fieldContext.onApply(applyPayload);
      setLogLines((prev) => [...prev, `系統：已套用到 ${applyPayload.targetField}`]);
      setApplyPayload(null);
      setMissingApplyKeys([]);
      baselineConflictVersionRef.current = fieldContext.conflictVersion || baselineConflictVersionRef.current;
      setChatStatus("idle");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "套用失敗";
      setLogLines((prev) => [...prev, `系統：${msg}`]);
      setChatStatus("error");
      onError(msg);
    }
  };

  return (
    <Sheet
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (nextOpen) {
          baselineConflictVersionRef.current = fieldContext?.conflictVersion || null;
        } else {
          setChatStatus("idle");
          setApplyPayload(null);
          setMissingApplyKeys([]);
          setPrompt("");
          setStreamingOutput("");
        }
      }}
    >
      <SheetTrigger
        render={
          <Button size="sm" variant="outline" className="h-7 gap-1.5 text-[11px]">
            <PlugZap className="h-3.5 w-3.5" />
            {launcherLabel}
          </Button>
        }
      />
      <SheetContent side="right" className="overflow-y-auto p-0 sm:max-w-xl">
        <SheetHeader className="border-b border-border/40">
          <SheetTitle>{fieldContext ? `討論這段：${fieldContext.fieldLabel}` : "直接在 Web 跟 Claude Code CLI 討論"}</SheetTitle>
          <SheetDescription>
            {fieldContext ? "已預載欄位上下文，不需要再手動補背景。" : "走本機 helper，不需輸入 API key。"}
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-3 p-4">
          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-background/70 px-3 py-2">
            <div className="text-[11px] text-muted-foreground">
              對話狀態：<span className="text-foreground">{statusText[chatStatus]}</span>
            </div>
            <Badge variant="outline" className="text-[10px]">
              rules {REDACTION_RULES_VERSION}
            </Badge>
          </div>

          <div className="rounded-lg border border-border/40 bg-background/70 p-2.5">
            <div className="mb-2 text-[11px] font-medium text-foreground">首次使用（2 步）</div>
            <div className="space-y-2 text-[11px]">
              <div className="rounded border border-border/30 bg-card/60 p-2">
                <div className="mb-1 text-muted-foreground">1. 一鍵安裝 helper</div>
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
              <div className="rounded border border-border/30 bg-card/60 p-2">
                <div className="mb-1 text-muted-foreground">2. 設定 token 並啟動 helper（推薦）</div>
                <input
                  value={helperToken}
                  onChange={(e) => setHelperTokenState(e.target.value)}
                  placeholder="貼一組 token（例如公司提供給你的）"
                  className="mb-2 h-8 w-full rounded-md border border-border/50 bg-background px-2.5 text-xs text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                />
                <code className="block overflow-x-auto whitespace-nowrap text-foreground">{helperSecureStartCommand}</code>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  token 就是這頁和你本機 helper 的配對碼，任意字串即可。
                </p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  安全預設：只綁定 127.0.0.1、限制本站網域、且禁用 Claude 工具（只做文字討論）。
                </p>
                <div className="mt-2 flex justify-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-[10px]"
                    onClick={async () => {
                      setHelperTokenState(generateHelperToken());
                    }}
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
              <div className="flex items-center justify-between rounded border border-border/30 bg-card/60 px-2 py-1.5">
                <span className="text-muted-foreground">進階設定（URL / CWD）</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => setShowAdvancedSettings((v) => !v)}
                >
                  {showAdvancedSettings ? "收起" : "展開"}
                </Button>
              </div>
            </div>
          </div>

          <div className="grid gap-2">
            <div className="flex items-center justify-between rounded border border-border/30 bg-card/60 px-2 py-1.5">
              <span className="text-[11px] text-muted-foreground">模型</span>
              <select
                value={helperModel}
                onChange={(e) => setHelperModelState(e.target.value)}
                className="h-7 min-w-[140px] rounded-md border border-border/50 bg-background px-2 text-[11px] text-foreground outline-none focus:border-primary/50"
              >
                <option value="sonnet">Sonnet（預設）</option>
                <option value="opus">Opus</option>
                <option value="haiku">Haiku</option>
              </select>
            </div>
            {showAdvancedSettings && (
              <>
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
              </>
            )}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">狀態：{healthText}</span>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-[11px]"
                disabled={checkingHealth}
                onClick={runHealthCheck}
              >
                {checkingHealth ? "檢查中..." : "檢查 helper"}
              </Button>
            </div>
          </div>

          {capability && (
            <div className="space-y-2 rounded-lg border border-border/40 bg-background/70 p-3">
              {!capability.mcpOk && (
                <div className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200">
                  ZenOS 連線失敗：AI 仍可對話，但無法讀寫資料。
                </div>
              )}
              {capability.missingSkills && capability.missingSkills.length > 0 && (
                <div className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200">
                  部分 skill 未載入：{capability.missingSkills.join(", ")}
                </div>
              )}
              <div className="text-[11px] text-muted-foreground">
                已載入 skill：{capability.skillsLoaded.length > 0 ? capability.skillsLoaded.join(", ") : "未偵測到"}
              </div>
            </div>
          )}

          {contextPack && (
            <details className="rounded-lg border border-border/40 bg-background/70 p-3">
              <summary className="cursor-pointer text-[11px] font-medium text-foreground">已載入上下文清單</summary>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] text-muted-foreground">
                {JSON.stringify(contextPack, null, 2)}
              </pre>
            </details>
          )}

          <div className="rounded-lg border border-border/40 bg-background/70 p-2.5">
            <div className="mb-2 text-[11px] text-muted-foreground">會話 ID：{conversationId}</div>
            <div ref={chatViewportRef} className="max-h-[280px] space-y-2 overflow-y-auto rounded border border-border/30 bg-card/50 p-2 text-xs">
              {logLines.length === 0 ? (
                <p className="text-muted-foreground">尚無對話。輸入後會在這裡串流顯示。</p>
              ) : (
                logLines.map((line, index) => {
                  const isUser = line.startsWith("你：");
                  const isAssistant = line.startsWith("Claude：");
                  const content = line.replace(/^(你|Claude|系統)：\s*/, "");
                  return (
                    <div key={`${index}-${line.slice(0, 20)}`} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[86%] whitespace-pre-wrap rounded-lg px-3 py-2 ${
                          isUser
                            ? "bg-primary/20 text-primary-foreground"
                            : isAssistant
                              ? "bg-emerald-500/10 text-foreground"
                              : "bg-muted/30 text-muted-foreground"
                        }`}
                      >
                        {content}
                      </div>
                    </div>
                  );
                })
              )}
              {running && streamingOutput && (
                <div className="flex justify-start">
                  <div className="max-w-[86%] whitespace-pre-wrap rounded-lg bg-emerald-500/10 px-3 py-2 text-foreground">
                    {streamingOutput}
                    <span className="ml-1 inline-block h-3 w-1 animate-pulse rounded bg-foreground/60 align-middle" />
                  </div>
                </div>
              )}
            </div>
          </div>

          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              fieldContext
                ? `可補充你想調整的方向；直接送出也可以，系統已帶入 ${fieldContext.fieldLabel} 背景`
                : "輸入你想跟 AI 討論的策略問題"
            }
            className="min-h-[92px] w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
          />

          {missingApplyKeys.length > 0 && (
            <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              結構化結果缺少鍵：{missingApplyKeys.join(", ")}
            </div>
          )}

          {applyPayload && chatStatus === "apply-ready" && (
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
              <div className="mb-2 text-xs font-medium text-foreground">可套用變更：{applyPayload.targetField}</div>
              <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-muted-foreground">
                {typeof applyPayload.value === "string" ? applyPayload.value : JSON.stringify(applyPayload.value, null, 2)}
              </pre>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2">
            {fieldContext?.onApply ? (
              <div className="text-xs text-muted-foreground">AI 輸出結構化結果後，可直接套用到欄位。</div>
            ) : onUseOutput ? (
              <div className="text-xs text-muted-foreground">回覆完成後會自動帶回呼叫端。</div>
            ) : (
              <div className="text-xs text-muted-foreground">提示：進入活動後可把回覆直接帶回策略欄位。</div>
            )}
            <div className="flex items-center gap-2">
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
                disabled={running || chatStatus === "applying" || (!fieldContext && !prompt.trim())}
                onClick={sendMessage}
              >
                {running ? "執行中..." : fieldContext ? "開始討論" : "送出"}
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function StrategyPlanner({
  campaign,
  strategy,
  onSave,
  onError,
  saving,
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
  }) => Promise<void>;
  onError: (message: string) => void;
  saving: boolean;
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
  const canSave =
    parsedAudience.length > 0 &&
    tone.trim().length > 0 &&
    coreMessage.trim().length > 0 &&
    parsedPlatforms.length > 0 &&
    (campaign.projectType === "short_term" || (frequency.trim().length > 0 && Object.keys(parsedContentMix).length > 0)) &&
    !saving;

  return (
    <div className="rounded-xl border border-border/40 bg-card/70 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-foreground">建立行銷寫作計畫</h3>
          <p className="mt-1 text-xs text-muted-foreground">先和 AI 討論策略，不用你手填一堆欄位。</p>
        </div>
        <CoworkChatSheet
          campaignId={campaign.id}
          launcherLabel="討論這段"
          onError={onError}
          fieldContext={{
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
              setAudience(formatCsv(nextAudience));
              setTone(nextTone);
              setCoreMessage(nextCoreMessage);
              setPlatforms(formatCsv(nextPlatforms));
              setFrequency(nextFrequency);
              setContentMix(formatContentMix(nextContentMix));
              setCampaignGoal(nextCampaignGoal);
              setCtaStrategy(nextCtaStrategy);
              setReferenceMaterials(
                formatCsv(nextReferenceMaterials)
              );
              setShowManual(true);
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
              });
            },
          }}
        />
      </div>

      <div className="rounded-md border border-border/40 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
        直接按右上「AI 討論（Beta）」對話即可。AI 回覆會自動套用到下方策略欄位。
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
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <input
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              placeholder="目標受眾（逗號分隔）"
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
            />
            <input
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder="語氣風格"
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
            />
            <input
              value={coreMessage}
              onChange={(e) => setCoreMessage(e.target.value)}
              placeholder="核心訊息"
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
            />
            <input
              value={platforms}
              onChange={(e) => setPlatforms(e.target.value)}
              placeholder="發文平台（逗號分隔）"
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
            />
            {campaign.projectType === "long_term" && (
              <>
                <input
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value)}
                  placeholder="發文頻率（例如每週 2 篇）"
                  className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                />
                <input
                  value={contentMix}
                  onChange={(e) => setContentMix(e.target.value)}
                  placeholder="內容比例（例如 education:70, product:30）"
                  className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
                />
              </>
            )}
            <input
              value={campaignGoal}
              onChange={(e) => setCampaignGoal(e.target.value)}
              placeholder="活動目標（選填）"
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
            />
            <input
              value={ctaStrategy}
              onChange={(e) => setCtaStrategy(e.target.value)}
              placeholder="CTA 策略（選填）"
              className="h-9 rounded-md border border-border/50 bg-background px-3 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
            />
          </div>
          <textarea
            value={referenceMaterials}
            onChange={(e) => setReferenceMaterials(e.target.value)}
            placeholder="參考素材（連結或關鍵字，逗號分隔）"
            className="mt-2 min-h-[60px] w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 placeholder:text-muted-foreground/70 focus:border-primary/50"
          />
        </>
      )}

      <div className="mt-3 flex justify-end">
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

function StyleManager({
  campaign,
  styles,
  onSaveStyle,
  onError,
  saving,
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
}) {
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState<MarketingStyle["level"]>("project");
  const [platform, setPlatform] = useState("threads");
  const [content, setContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  const allStyles = [...styles.product, ...styles.platform, ...styles.project];

  const beginEdit = (style: MarketingStyle) => {
    setEditingId(style.id);
    setTitle(style.title);
    setLevel(style.level);
    setPlatform(style.platform || "threads");
    setContent(style.content);
  };

  return (
    <div className="rounded-xl border border-border/40 bg-card/70 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-foreground">文風管理</h3>
          <p className="mt-1 text-xs text-muted-foreground">先交付三層 style CRUD；預覽測試會在下一階段接 helper。</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[0.6rem]">
            {campaign.projectType === "long_term" ? "長期項目" : "短期活動"}
          </Badge>
          <CoworkChatSheet
            campaignId={campaign.id}
            launcherLabel="討論這段"
            onError={onError}
            fieldContext={{
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
            }}
          />
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
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs text-muted-foreground">預覽測試入口保留，會在 helper deep integration 補上。</div>
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

function TopicStarter({
  campaign,
  onCreateTopic,
  onError,
  creatingTopic,
}: {
  campaign: Campaign;
  onCreateTopic: (input: { topic: string; platform: string; brief: string }) => Promise<void>;
  onError: (message: string) => void;
  creatingTopic: boolean;
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
          <p className="mt-1 text-xs text-muted-foreground">建立後會進入草稿；下一步請到 Claude cowork 執行 <code>/marketing-generate</code>。</p>
        </div>
        <CoworkChatSheet
          campaignId={campaign.id}
          launcherLabel="討論這段"
          onError={onError}
            fieldContext={{
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
            }}
          />
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

function CampaignDetail({
  campaign,
  onBack,
  onReview,
  reviewingPostId,
  onCreateTopic,
  creatingTopic,
  onSaveStrategy,
  onError,
  savingStrategy,
  styles,
  onSaveStyle,
  savingStyle,
}: {
  campaign: Campaign;
  onBack: () => void;
  onReview: (postId: string, action: "approve" | "request_changes" | "reject") => void;
  reviewingPostId: string | null;
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
}) {
  const review = campaign.posts.filter((p) => requiresReview(p.status));
  const planned = campaign.posts.filter((p) => isPlannedStatus(p.status));
  const confirmed = campaign.posts.filter((p) => isConfirmedStatus(p.status));
  const scheduled = campaign.posts.filter((p) => p.status === "scheduled");
  const published = campaign.posts.filter((p) => p.status === "published");

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

      {campaign.blockReason && (
        <div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          <div>
            <div className="text-sm font-medium text-foreground">{campaign.blockReason}</div>
            <p className="mt-1 text-xs text-muted-foreground">解決後 AI 會自動開始準備內容。</p>
          </div>
        </div>
      )}

      <StrategyPlanner
        campaign={campaign}
        strategy={campaign.strategy}
        onSave={onSaveStrategy}
        onError={onError}
        saving={savingStrategy}
      />
      <StyleManager campaign={campaign} styles={styles} onSaveStyle={onSaveStyle} onError={onError} saving={savingStyle} />
      {campaign.strategy && <StrategyAndPlan strategy={campaign.strategy} contentPlan={campaign.contentPlan} />}
      <TopicStarter campaign={campaign} onCreateTopic={onCreateTopic} onError={onError} creatingTopic={creatingTopic} />

      {review.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-amber-400">待你確認</h3>
          {review.map((post) => (
            <PostCard
              key={post.id}
              post={post}
              onReview={onReview}
              isReviewing={reviewingPostId === post.id}
            />
          ))}
        </section>
      )}

      {planned.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-primary">規劃中</h3>
          {planned.map((post) => (
            <PostCard key={post.id} post={post} onReview={onReview} isReviewing={reviewingPostId === post.id} />
          ))}
        </section>
      )}

      {confirmed.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-primary">已確認</h3>
          {confirmed.map((post) => (
            <PostCard key={post.id} post={post} onReview={onReview} isReviewing={reviewingPostId === post.id} />
          ))}
        </section>
      )}

      {scheduled.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-chart-2">已排程</h3>
          {scheduled.map((post) => (
            <PostCard key={post.id} post={post} onReview={onReview} isReviewing={reviewingPostId === post.id} />
          ))}
        </section>
      )}

      {published.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">已發佈</h3>
          {published.map((post) => (
            <PostCard key={post.id} post={post} onReview={onReview} isReviewing={reviewingPostId === post.id} />
          ))}
        </section>
      )}
    </div>
  );
}

export default function MarketingPage() {
  const { user } = useAuth();
  const [campaignGroups, setCampaignGroups] = useState<CampaignGroup[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [projectStyles, setProjectStyles] = useState<MarketingStyleBuckets>({ product: [], platform: [], project: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewingPostId, setReviewingPostId] = useState<string | null>(null);
  const [creatingTopic, setCreatingTopic] = useState(false);
  const [creatingCampaign, setCreatingCampaign] = useState(false);
  const [savingStrategy, setSavingStrategy] = useState(false);
  const [savingStyle, setSavingStyle] = useState(false);

  const loadCampaigns = useCallback(async () => {
    if (!user) return;
    setError(null);
    const token = await user.getIdToken();
    const data = await getMarketingProjectGroups(token);
    setCampaignGroups(data);
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    loadCampaigns()
      .catch((err) => setError(err instanceof Error ? err.message : "載入失敗"))
      .finally(() => setLoading(false));
  }, [user, loadCampaigns]);

  useEffect(() => {
    if (!user || !selectedId) {
      setSelectedCampaign(null);
      setProjectStyles({ product: [], platform: [], project: [] });
      return;
    }
    let alive = true;
    user
      .getIdToken()
      .then(async (token) => {
        const [detail, styles] = await Promise.all([
          getMarketingProjectDetail(token, selectedId),
          getMarketingProjectStyles(token, selectedId),
        ]);
        return { detail, styles };
      })
      .then(({ detail, styles }) => {
        if (!alive) return;
        setSelectedCampaign(detail);
        setProjectStyles(styles);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "載入活動失敗");
      });
    return () => {
      alive = false;
    };
  }, [user, selectedId]);

  const campaigns = useMemo(() => campaignGroups.flatMap((group) => group.projects), [campaignGroups]);
  const selectedFromList = useMemo(
    () => campaigns.find((c) => c.id === selectedId) || null,
    [campaigns, selectedId]
  );

  const handleReview = useCallback(
    async (postId: string, action: "approve" | "request_changes" | "reject") => {
      if (!user || !selectedId) return;
      const comment =
        action === "approve"
          ? ""
          : window.prompt(action === "request_changes" ? "請輸入修改意見" : "請輸入退回原因", "") || "";
      setReviewingPostId(postId);
      try {
        const token = await user.getIdToken();
        await reviewMarketingPost(token, postId, { action, comment });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "審核失敗");
      } finally {
        setReviewingPostId(null);
      }
    },
    [user, selectedId]
  );

  const handleCreateTopic = useCallback(
    async ({ topic, platform, brief }: { topic: string; platform: string; brief: string }) => {
      if (!user || !selectedId) return;
      setCreatingTopic(true);
      try {
        const token = await user.getIdToken();
        await createMarketingTopic(token, selectedId, { topic, platform, brief });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "建立主題失敗");
      } finally {
        setCreatingTopic(false);
      }
    },
    [user, selectedId]
  );

  const handleCreateCampaign = useCallback(
    async ({
      productId,
      name,
      description,
      projectType,
      dateRange,
    }: {
      productId: string;
      name: string;
      description: string;
      projectType: "long_term" | "short_term";
      dateRange?: { start: string; end: string } | null;
    }) => {
      if (!user) return;
      setCreatingCampaign(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        const created = await createMarketingProject(token, {
          productId,
          name,
          description,
          projectType,
          dateRange,
        });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, created.id),
        ]);
        setCampaignGroups(list);
        setSelectedId(created.id);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "建立活動失敗");
      } finally {
        setCreatingCampaign(false);
      }
    },
    [user]
  );

  const handleSaveStrategy = useCallback(
    async (input: {
      audience: string[];
      tone: string;
      coreMessage: string;
      platforms: string[];
      frequency?: string;
      contentMix?: Record<string, number>;
      campaignGoal?: string;
      ctaStrategy?: string;
      referenceMaterials?: string[];
    }) => {
      if (!user || !selectedId) return;
      setSavingStrategy(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        await updateMarketingProjectStrategy(token, selectedId, {
          ...input,
          expectedUpdatedAt: selectedCampaign?.strategy?.updatedAt,
        });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "儲存策略失敗");
      } finally {
        setSavingStrategy(false);
      }
    },
    [user, selectedId, selectedCampaign?.strategy?.updatedAt]
  );

  const handleSaveStyle = useCallback(
    async (input: { id?: string; title: string; level: MarketingStyle["level"]; content: string; platform?: string }) => {
      if (!user || !selectedCampaign) return;
      setSavingStyle(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        if (input.id) {
          await updateMarketingStyle(token, input.id, { title: input.title, content: input.content });
        } else {
          await createMarketingStyle(token, {
            title: input.title,
            level: input.level,
            content: input.content,
            productId: input.level === "project" ? undefined : selectedCampaign.productId || undefined,
            projectId: input.level === "project" ? selectedCampaign.id : undefined,
            platform: input.level === "platform" ? input.platform : undefined,
          });
        }
        const styles = await getMarketingProjectStyles(token, selectedCampaign.id);
        setProjectStyles(styles);
      } catch (err) {
        setError(err instanceof Error ? err.message : "儲存文風失敗");
      } finally {
        setSavingStyle(false);
      }
    },
    [user, selectedCampaign]
  );

  const productOptions = useMemo(() => {
    const seen = new Set<string>();
    return campaignGroups
      .map((group) => group.product)
      .filter((product) => {
        const key = product.id || product.name;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }, [campaignGroups]);

  return (
    <AuthGuard>
      <div className="min-h-screen bg-background text-foreground">
        <AppNav />
        <main className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-foreground">行銷主控台</h1>
              <p className="text-sm text-muted-foreground">Paceriz</p>
            </div>
            <div className="flex items-center gap-2">
              <CoworkChatSheet
                campaignId={selectedId}
                onError={setError}
              />
              <PromptManagerSheet
                user={user ? { getIdToken: () => user.getIdToken() } : null}
                onError={setError}
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
              onCreateTopic={handleCreateTopic}
              creatingTopic={creatingTopic}
              onSaveStrategy={handleSaveStrategy}
              onError={setError}
              savingStrategy={savingStrategy}
              styles={projectStyles}
              onSaveStyle={handleSaveStyle}
              savingStyle={savingStyle}
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
    </AuthGuard>
  );
}
