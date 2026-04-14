import { serializeSanitizedContextValue } from "@/config/ai-redaction-rules";
import type { MarketingProject, MarketingStyleBuckets, Post } from "@/lib/marketing-api";

export type DiscussionFieldId = "strategy" | "topic" | "style" | "schedule" | "review";
export type DiscussionPhase = "strategy" | "schedule" | "intel" | "generate" | "adapt" | "publish";
export type ChatStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "awaiting-local-approval"
  | "apply-ready"
  | "applying"
  | "error";
export type ProjectStage = "strategy" | "schedule" | "intel" | "generate" | "review" | "publish";

export interface ContextPack {
  field_id: DiscussionFieldId;
  field_value: string | null;
  project_summary: string;
  current_phase: DiscussionPhase;
  suggested_skill: string;
  related_context?: string;
}

export interface StructuredApplyPayload {
  targetField: DiscussionFieldId;
  value: unknown;
}

export interface FieldDiscussionConfig {
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

export function formatCsv(values: string[] | undefined): string {
  return (values || []).join(", ");
}

export function parseCsv(value: string): string[] {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function formatContentMix(contentMix: Record<string, number> | undefined): string {
  if (!contentMix || Object.keys(contentMix).length === 0) return "";
  return Object.entries(contentMix)
    .map(([key, value]) => `${key}:${value}`)
    .join(", ");
}

export function parseContentMix(value: string): Record<string, number> {
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

export function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

export function buildProjectSummary(project: MarketingProject): string {
  const parts = [
    project.name,
    project.projectType === "long_term" ? "長期經營" : "短期活動",
    project.description,
  ].filter(Boolean);
  if (project.strategy?.coreMessage) {
    parts.push(`核心訊息：${project.strategy.coreMessage}`);
  }
  if (project.strategy?.platforms?.length) {
    parts.push(`平台：${project.strategy.platforms.join(" / ")}`);
  }
  return truncateText(parts.join(" / "), 500);
}

export function buildContextPack(input: {
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

export function buildDiscussionPrompt(field: FieldDiscussionConfig, userPrompt: string): string {
  const contextPack = buildContextPack({
    fieldId: field.fieldId,
    currentPhase: field.currentPhase,
    suggestedSkill: field.suggestedSkill,
    projectSummary: field.projectSummary,
    fieldValue: field.fieldValue,
    relatedContext: field.relatedContext,
  });
  const schemaExamples: Record<DiscussionFieldId, string> = {
    strategy:
      '{"target_field":"strategy","value":{"audience":["跑步新手"],"tone":"專業但親切","core_message":"先建立習慣再談進階裝備","platforms":["Threads","Blog"]}}',
    topic:
      '{"target_field":"topic","value":{"title":"跑步新手 7 天挑戰","brief":"聚焦新手容易卡關的三個理由","platform":"Threads"}}',
    style:
      '{"target_field":"style","value":{"title":"Threads 親切教練風","content":"# 語氣\\n- 親切\\n- 直接\\n","platform":"Threads"}}',
    schedule:
      '{"target_field":"schedule","value":[{"date":"2026-04-20","platform":"Threads","topic":"跑步新手暖身","reason":"銜接前一篇 FAQ"}]}',
    review:
      '{"target_field":"review","value":{"summary":"指出 CTA 過弱","suggestion":"把 CTA 改成具體下載動作"}}',
  };
  const baseInstruction = contextPack.field_value
    ? `以下是目前的${field.fieldLabel}，請先給修改建議，再整理成結構化結果。`
    : `請幫我設定這個項目的${field.fieldLabel}，先用白話說明你的建議，再整理成結構化結果。`;
  const userLine = userPrompt.trim()
    ? `使用者補充：${userPrompt.trim()}`
    : "使用者補充：若資訊不足，先提出最多 3 個澄清問題，再給暫定方案。";
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

export function validateStructuredValue(targetField: DiscussionFieldId, value: unknown): string[] {
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

export function parseStructuredApplyPayload(raw: string, expectedFieldId?: DiscussionFieldId): { payload: StructuredApplyPayload | null; missingKeys: string[] } {
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

export function parseCoworkStreamLine(line: string): { delta: string; debug: string } {
  const raw = line.trim();
  if (!raw) return { delta: "", debug: "" };
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if ("target_field" in parsed && "value" in parsed) {
      return { delta: raw, debug: "" };
    }
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

export function requiresReview(status: Post["status"]): boolean {
  return status === "draft_generated" || status === "platform_adapted";
}

export function isPlannedStatus(status: Post["status"]): boolean {
  return status === "topic_planned" || status === "intel_ready";
}

export function isConfirmedStatus(status: Post["status"]): boolean {
  return status === "draft_confirmed" || status === "platform_confirmed";
}

export function statusConfig(status: Post["status"]) {
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

export function campaignStatusConfig(status: MarketingProject["status"]) {
  switch (status) {
    case "active":
      return { dot: "bg-primary", badge: "border-primary/30 bg-primary/10 text-primary", label: "進行中" };
    case "blocked":
      return { dot: "bg-destructive", badge: "border-destructive/30 bg-destructive/10 text-destructive", label: "暫停" };
    case "completed":
      return { dot: "bg-muted-foreground", badge: "border-border/40 bg-muted/20 text-muted-foreground", label: "已結束" };
  }
}

export function deriveProjectStage(project: MarketingProject): ProjectStage {
  if (!project.strategy?.documentId) return "strategy";
  if (!project.contentPlan?.length && project.posts.length === 0) return "schedule";
  if (project.posts.some((post) => post.status === "topic_planned")) return "intel";
  if (project.posts.some((post) => post.status === "intel_ready")) return "generate";
  if (project.posts.some((post) => requiresReview(post.status))) return "review";
  return "publish";
}

export function primaryCtaForProject(project: MarketingProject): { label: string; hint: string } {
  const stage = deriveProjectStage(project);
  switch (stage) {
    case "strategy":
      return { label: "先完成策略", hint: "先用「討論這段」或手動儲存策略，後面排程與主題才會解鎖。" };
    case "schedule":
      return { label: "先產生排程", hint: "下一步先跑 /marketing-plan，把未來 1-2 週主題排出來。" };
    case "intel":
      return { label: "先補情報", hint: "主題已建立，先跑 /marketing-intel 蒐集近期訊號。" };
    case "generate":
      return { label: "產生文案", hint: "情報已就緒，下一步跑 /marketing-generate 產生主文案。" };
    case "review":
      return { label: "確認文案", hint: "有待確認內容，先做審核再進下一階段。" };
    case "publish":
      return { label: "安排發佈", hint: "已可進入發佈。若還沒排程，先跑 /marketing-publish。" };
  }
}

export function postNextStepHint(post: Post): string | null {
  if (post.status === "topic_planned") {
    return "下一步先執行 /marketing-intel 補齊情報，或直接跑 /marketing-generate 產生初稿。";
  }
  if (post.status === "intel_ready") {
    return "下一步到 Claude cowork 執行 /marketing-generate 產生正式文案。";
  }
  if (post.status === "draft_confirmed") {
    return "主文案已確認，下一步直接做 /marketing-adapt 產生各平台版本。";
  }
  if (post.status === "platform_confirmed") {
    return "平台版本已確認，下一步直接做 /marketing-publish 建立排程。";
  }
  return null;
}

export function composeStyleMarkdown(styles: MarketingStyleBuckets, preferredPlatform?: string): string {
  const lines: string[] = [];
  if (styles.product[0]?.content) {
    lines.push("# Product Style", styles.product[0].content.trim());
  }
  const platformStyle =
    styles.platform.find((item) => item.platform?.toLowerCase() === String(preferredPlatform || "").toLowerCase()) ||
    styles.platform[0];
  if (platformStyle?.content) {
    lines.push("# Platform Style", platformStyle.content.trim());
  }
  if (styles.project[0]?.content) {
    lines.push("# Project Style", styles.project[0].content.trim());
  }
  return lines.filter(Boolean).join("\n\n").trim();
}

export function stylePreviewPrompt(input: {
  styles: MarketingStyleBuckets;
  topic: string;
  platform?: string;
  projectName: string;
}): string {
  const merged = composeStyleMarkdown(input.styles, input.platform);
  return [
    "你是 ZenOS 文風預覽助手。",
    `請用以下文風，生成一段關於「${input.topic}」的測試文案。`,
    `project=${input.projectName}`,
    input.platform ? `platform=${input.platform}` : "",
    "",
    merged || "# No Style\n目前沒有可用 style，請用中性品牌語氣。",
  ]
    .filter(Boolean)
    .join("\n");
}

export function nextChatStatus(current: ChatStatus, event: "send" | "message" | "permission_request" | "permission_result" | "apply_available" | "apply_start" | "apply_done" | "error" | "cancel" | "reset"): ChatStatus {
  switch (event) {
    case "send":
      return "loading";
    case "message":
      return "streaming";
    case "permission_request":
      return "awaiting-local-approval";
    case "permission_result":
      return "streaming";
    case "apply_available":
      return "apply-ready";
    case "apply_start":
      return "applying";
    case "apply_done":
      return "idle";
    case "error":
      return "error";
    case "cancel":
      return "idle";
    case "reset":
      return "idle";
  }
  return current;
}
