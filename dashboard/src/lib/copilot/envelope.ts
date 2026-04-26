import type {
  CopilotClaudeCodeBootstrap,
  CopilotEntryConfig,
  CopilotScopeEnvelope,
} from "@/lib/copilot/types";

export interface CopilotPromptHistoryMessage {
  role: string;
  content: string;
}

const MAX_HISTORY_MESSAGES = 6;
const MAX_HISTORY_MESSAGE_CHARS = 18000;
const MAX_HISTORY_TOTAL_CHARS = 48000;

function renderScope(scope: CopilotScopeEnvelope): string[] {
  return [
    `workspace_id=${scope.workspace_id || ""}`,
    `project=${scope.project || ""}`,
    `product_id=${scope.product_id || ""}`,
    `entity_ids=${(scope.entity_ids || []).join(",")}`,
    `campaign_id=${scope.campaign_id || ""}`,
    `deal_id=${scope.deal_id || ""}`,
    `scope_label=${scope.scope_label}`,
  ];
}

function renderClaudeCodeBootstrap(
  bootstrap: CopilotClaudeCodeBootstrap | undefined
): string[] {
  if (!bootstrap) return [];
  return [
    "[CLAUDE_CODE_BOOTSTRAP]",
    `use_project_claude_config=${bootstrap.use_project_claude_config ? "true" : "false"}`,
    `required_skills=${(bootstrap.required_skills || []).join(",")}`,
    `governance_topics=${(bootstrap.governance_topics || []).join(",")}`,
    `verify_zenos_write=${bootstrap.verify_zenos_write ? "true" : "false"}`,
    ...(bootstrap.execution_contract || []).map((line, index) => `execution_contract_${index + 1}=${line}`),
    "",
  ];
}

function trimMiddle(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  const headChars = Math.floor(maxChars * 0.65);
  const tailChars = maxChars - headChars;
  return [
    value.slice(0, headChars).trimEnd(),
    "\n...[truncated middle]...\n",
    value.slice(-tailChars).trimStart(),
  ].join("");
}

function renderRecentConversation(history: CopilotPromptHistoryMessage[] | undefined): string[] {
  if (!history || history.length === 0) return [];
  const selected = history
    .filter((message) => message.content.trim())
    .slice(-MAX_HISTORY_MESSAGES);
  if (selected.length === 0) return [];

  let remaining = MAX_HISTORY_TOTAL_CHARS;
  const rendered: string[] = [];
  for (const message of selected) {
    if (remaining <= 0) break;
    const role = message.role || "unknown";
    const trimmed = trimMiddle(message.content.trim(), Math.min(MAX_HISTORY_MESSAGE_CHARS, remaining));
    rendered.push(`role=${role}\n${trimmed}`);
    remaining -= trimmed.length;
  }

  if (rendered.length === 0) return [];
  return [
    "[RECENT_CONVERSATION]",
    "This is the visible chat history immediately before USER_INPUT. Use it to resolve references like '這份文件', '上面那個', '入 ZenOS', or '剛剛的內容'.",
    ...rendered.map((item, index) => `--- message_${index + 1} ---\n${item}`),
    "",
  ];
}

export function buildCopilotPromptEnvelope(
  entry: CopilotEntryConfig,
  userInput: string,
  recentConversation?: CopilotPromptHistoryMessage[]
): string {
  const promptBody = entry.build_prompt(userInput).trim();
  const contextPack = entry.get_context_pack ? entry.get_context_pack() : entry.context_pack;
  return [
    "[AI_RAIL]",
    `intent_id=${entry.intent_id}`,
    `mode=${entry.mode}`,
    `session_policy=${entry.session_policy}`,
    entry.suggested_skill ? `suggested_skill=${entry.suggested_skill}` : "",
    "",
    "[SCOPE]",
    ...renderScope(entry.scope),
    "",
    ...renderClaudeCodeBootstrap(entry.claude_code_bootstrap),
    "[CONTEXT_PACK]",
    JSON.stringify(contextPack, null, 2),
    "",
    ...renderRecentConversation(recentConversation),
    "[USER_INPUT]",
    userInput.trim() || "(empty)",
    "",
    "[TASK_PROMPT]",
    promptBody || "(empty)",
  ]
    .filter(Boolean)
    .join("\n");
}
