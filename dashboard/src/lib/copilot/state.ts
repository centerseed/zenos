import type { CopilotChatStatus, CopilotEntryConfig } from "@/lib/copilot/types";

export type CopilotStateEvent =
  | "send"
  | "message"
  | "permission_request"
  | "permission_result"
  | "apply_available"
  | "apply_start"
  | "apply_done"
  | "error"
  | "cancel"
  | "reset";

export function nextCopilotStatus(
  _current: CopilotChatStatus,
  event: CopilotStateEvent
): CopilotChatStatus {
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
    case "cancel":
    case "reset":
      return "idle";
    case "error":
      return "error";
  }
}

function joinDefined(parts: Array<string | undefined | null>): string {
  return parts
    .map((part) => part?.trim())
    .filter((part): part is string => Boolean(part))
    .join(":");
}

export function getCopilotConversationKey(entry: CopilotEntryConfig): string {
  const scope = entry.scope;
  return joinDefined([
    entry.intent_id,
    scope.workspace_id,
    scope.project,
    scope.product_id,
    scope.campaign_id,
    scope.deal_id,
    scope.entity_ids?.join(","),
  ]);
}

export function usesScopedResume(entry: CopilotEntryConfig): boolean {
  return entry.session_policy === "scoped_resume";
}
