import type { CopilotEntryConfig, CopilotScopeEnvelope } from "@/lib/copilot/types";

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

export function buildCopilotPromptEnvelope(
  entry: CopilotEntryConfig,
  userInput: string
): string {
  const promptBody = entry.build_prompt(userInput).trim();
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
    "[CONTEXT_PACK]",
    JSON.stringify(entry.context_pack, null, 2),
    "",
    "[USER_INPUT]",
    userInput.trim() || "(empty)",
    "",
    "[TASK_PROMPT]",
    promptBody || "(empty)",
  ]
    .filter(Boolean)
    .join("\n");
}
