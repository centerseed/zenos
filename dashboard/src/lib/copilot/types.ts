export type CopilotMode = "chat" | "apply" | "artifact";
export type CopilotLaunchBehavior = "manual" | "auto_start";
export type CopilotSessionPolicy = "scoped_resume" | "ephemeral";
export type CopilotChatStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "awaiting-local-approval"
  | "apply-ready"
  | "applying"
  | "error";

export interface CopilotScopeEnvelope {
  workspace_id?: string;
  project?: string;
  product_id?: string;
  entity_ids?: string[];
  campaign_id?: string;
  deal_id?: string;
  scope_label: string;
}

export interface StructuredResult {
  target: string;
  value: unknown;
  summary?: string;
  missing_keys?: string[];
}

export interface CopilotClaudeCodeBootstrap {
  use_project_claude_config?: boolean;
  required_skills?: string[];
  governance_topics?: string[];
  verify_zenos_write?: boolean;
  execution_contract?: string[];
}

export interface CopilotEntryConfig {
  intent_id: string;
  title: string;
  description?: string;
  mode: CopilotMode;
  launch_behavior: CopilotLaunchBehavior;
  session_policy: CopilotSessionPolicy;
  suggested_skill?: string;
  claude_code_bootstrap?: CopilotClaudeCodeBootstrap;
  scope: CopilotScopeEnvelope;
  context_pack: Record<string, unknown>;
  get_context_pack?: () => Record<string, unknown>;
  write_targets?: string[];
  build_prompt: (input: string) => string;
  parse_structured_result?: (raw: string) => StructuredResult | null;
  on_apply?: (result: StructuredResult) => void | Promise<void>;
}

export interface ParsedStructuredResult {
  result: StructuredResult | null;
  missingKeys: string[];
}
