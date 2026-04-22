"use client";

import { useMemo, useState } from "react";
import { CopilotChatViewport } from "@/components/ai/CopilotChatViewport";
import { HelperSetupDialog } from "@/components/ai/HelperSetupDialog";
import { CopilotInputBar } from "@/components/ai/CopilotInputBar";
import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import { buildTaskHubCopilotEntry } from "@/features/tasks/taskHubCopilot";
import type { TaskHubSnapshot } from "@/features/tasks/taskHub";
import { useAuth } from "@/lib/auth";
import { resolveCopilotWorkspaceId } from "@/lib/copilot/scope";
import { useCopilotChat } from "@/lib/copilot/useCopilotChat";

export function TaskHubRail({
  snapshot,
  open,
  onOpenChange,
}: {
  snapshot: TaskHubSnapshot;
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [helperDialogOpen, setHelperDialogOpen] = useState(false);
  const { partner } = useAuth();
  const workspaceId = resolveCopilotWorkspaceId(partner);
  const entry = useMemo(() => buildTaskHubCopilotEntry({ snapshot, workspaceId }), [snapshot, workspaceId]);
  const { status, connectorStatus, messages, streamingText, capability, lastError, send, cancel, retry } =
    useCopilotChat(entry);
  const visibleMessages = useMemo(() => messages.filter((message) => message.role !== "system"), [messages]);
  const helperIssue = useMemo(() => {
    if (connectorStatus === "checking") return "正在檢查 helper";
    if (connectorStatus === "disconnected") return "helper 未連線";
    if (capability?.missingSkills?.length) return `缺 skill：${capability.missingSkills.join("、")}`;
    if (lastError) return lastError;
    return null;
  }, [capability?.missingSkills, connectorStatus, lastError]);
  const helperHealthy = connectorStatus === "connected" && !helperIssue;

  return (
    <CopilotRailShell
      open={open}
      onOpenChange={onOpenChange}
      entry={entry}
      chatStatus={status}
      connectorStatus={connectorStatus}
      desktopInline
      diagnostics={
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span
            style={{
              color: helperHealthy ? "var(--zen-jade, #5f7a45)" : "var(--zen-vermillion, #b63a2c)",
            }}
          >
            {helperHealthy ? "Helper 已連線" : helperIssue || "Helper 需要修復"}
          </span>
          {!helperHealthy ? (
            <button
              type="button"
              onClick={() => setHelperDialogOpen(true)}
              className="border bd-hair px-2 py-1 text-[11px] text-foreground"
            >
              設定 helper
            </button>
          ) : null}
        </div>
      }
      footer={
        <CopilotInputBar
          status={status}
          onSend={(input) => void send(input)}
          onCancel={() => void cancel()}
          onRetry={() => void retry()}
          hasStructuredResult={false}
          canSendEmpty
          sendLabel={messages.length === 0 ? "開始討論" : "送出"}
          placeholder="直接問全產品 milestone、plan、risk、blocker 或下一步"
        />
      }
    >
      <div data-testid="task-hub-recap-panel">
        <CopilotChatViewport
          messages={visibleMessages}
          streamingText={streamingText}
          isStreaming={status === "loading" || status === "streaming"}
          emptyStateTitle="Task Copilot"
          emptyStateDescription="先問哪個產品、哪個 milestone 或哪個 plan 最值得往下看。"
        />
      </div>
      <HelperSetupDialog
        open={helperDialogOpen}
        onOpenChange={setHelperDialogOpen}
        workspaceId={workspaceId}
      />
    </CopilotRailShell>
  );
}
