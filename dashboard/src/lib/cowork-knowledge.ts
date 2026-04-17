import type { GraphContextResponse } from "@/lib/api";

export const COWORK_MAX_TURNS = 10;

export type SourcePreference = "graph_derivable" | "user_required" | "mixed";

export interface TargetFieldDescriptor {
  id: string;
  label: string;
  source_preference: SourcePreference;
}

export interface SourceCitation {
  node_id: string;
  node_name: string;
  field_ids?: string[];
}

interface MarketingPromptFieldContext {
  fieldLabel: string;
  currentPhase: string;
  projectSummary: string;
  fieldValue: unknown;
  relatedContext?: string;
}

export const MARKETING_STRATEGY_TARGET_FIELDS: TargetFieldDescriptor[] = [
  { id: "audience", label: "目標受眾", source_preference: "graph_derivable" },
  { id: "tone", label: "品牌語氣", source_preference: "graph_derivable" },
  { id: "core_message", label: "核心訊息", source_preference: "graph_derivable" },
  { id: "platforms", label: "發文平台", source_preference: "user_required" },
  { id: "frequency", label: "發文頻率", source_preference: "user_required" },
  { id: "content_mix", label: "內容比例", source_preference: "user_required" },
  { id: "cta_strategy", label: "CTA 策略", source_preference: "user_required" },
];

function renderTargetFields(targetFields: TargetFieldDescriptor[]): string {
  return JSON.stringify(targetFields, null, 2);
}

export function renderGraphContextBlock(graphContext: GraphContextResponse | null): string {
  if (!graphContext) return "graph_context=null";
  return `graph_context=${JSON.stringify(graphContext, null, 2)}`;
}

export function graphContextUnavailableNotice(): string {
  return "知識圖譜暫時無法讀取，AI 將以對話內容為準。";
}

export function buildMarketingKnowledgePrompt(
  field: MarketingPromptFieldContext,
  userPrompt: string,
  options: {
    graphContext: GraphContextResponse | null;
    targetFields?: TargetFieldDescriptor[];
  }
): string {
  const targetFields = options.targetFields ?? MARKETING_STRATEGY_TARGET_FIELDS;
  const userLine = userPrompt.trim()
    ? `使用者補充：${userPrompt.trim()}`
    : "使用者補充：若資訊不足，請先列出你能從圖譜推得的草案，再只追問下一個必要欄位。";
  const fallbackInstruction =
    options.graphContext?.fallback_mode === "l1_tags_only"
      ? "若 graph_context.fallback_mode=l1_tags_only，首輪必須明說目前只有基本產品資訊，以下草案僅基於產品 tags，並在 JSON 帶 confidence=\"low\"。"
      : "";

  return [
    "你是 ZenOS 行銷協作助手。",
    "你要幫使用者完成策略欄位的漸進式預填。",
    "規則：先處理所有 graph_derivable 欄位；若沒有足夠依據，必須明說缺少依據，不得捏造引用。",
    "規則：後續每一輪最多只追問一個 user_required 欄位；若使用者說先跳過，要把該欄位列到 pending_fields。",
    "規則：當使用者說『就這樣』『整理結果』或要套用時，輸出一段 ```json```，格式如下。",
    'JSON schema: {"target_field":"strategy","value":{"audience":[],"tone":"","core_message":"","platforms":[],"frequency":"","content_mix":{},"cta_strategy":"","pending_fields":[],"confidence":"high|medium|low","source_citations":[{"node_id":"","node_name":"","field_ids":["audience"]}]}}',
    fallbackInstruction,
    `target_fields=${renderTargetFields(targetFields)}`,
    renderGraphContextBlock(options.graphContext),
    `field_label=${field.fieldLabel}`,
    `current_phase=${field.currentPhase}`,
    `project_summary=${field.projectSummary}`,
    `existing_value=${JSON.stringify(field.fieldValue, null, 2)}`,
    field.relatedContext ? `related_context=${field.relatedContext}` : "",
    userLine,
  ]
    .filter(Boolean)
    .join("\n");
}

export function buildCrmKnowledgePrompt(options: {
  promptLabel: string;
  baseContext: Record<string, unknown>;
  graphContext: GraphContextResponse | null;
  userMessage?: string;
  followUp?: boolean;
}): string {
  return [
    options.promptLabel,
    "",
    options.followUp ? "請延續前面的 briefing，並優先引用 graph_context 中的具體節點。" : "請準備會議 briefing，並優先引用 graph_context 中的具體節點。",
    "若 graph_context 不足，只能明說目前依據不足，不能假裝讀過不存在的模組。",
    renderGraphContextBlock(options.graphContext),
    `context_pack=${JSON.stringify(options.baseContext, null, 2)}`,
    options.userMessage ? `使用者補充：${options.userMessage}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export function normalizeSourceCitations(value: unknown): SourceCitation[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const record = item as Record<string, unknown>;
      const nodeId = String(record.node_id || record.nodeId || "").trim();
      const nodeName = String(record.node_name || record.nodeName || "").trim();
      if (!nodeId || !nodeName) return null;
      const fieldIdsRaw = record.field_ids ?? record.fieldIds;
      const field_ids = Array.isArray(fieldIdsRaw) ? fieldIdsRaw.map(String).filter(Boolean) : undefined;
      return { node_id: nodeId, node_name: nodeName, ...(field_ids && field_ids.length > 0 ? { field_ids } : {}) };
    })
    .filter((item): item is SourceCitation => item !== null);
}
