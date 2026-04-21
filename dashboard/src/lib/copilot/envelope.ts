import type {
  CopilotClaudeCodeBootstrap,
  CopilotEntryConfig,
  CopilotScopeEnvelope,
} from "@/lib/copilot/types";

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

export function buildCopilotPromptEnvelope(
  entry: CopilotEntryConfig,
  userInput: string
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
    "[USER_INPUT]",
    userInput.trim() || "(empty)",
    "",
    "[TASK_PROMPT]",
    promptBody || "(empty)",
  ]
    .filter(Boolean)
    .join("\n");
}
