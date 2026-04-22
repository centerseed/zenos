"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CopilotChatViewport } from "@/components/ai/CopilotChatViewport";
import { HelperSetupDialog } from "@/components/ai/HelperSetupDialog";
import { CopilotInputBar } from "@/components/ai/CopilotInputBar";
import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import { buildProjectRecapEntry } from "@/features/projects/projectCopilot";
import { useAuth } from "@/lib/auth";
import { resolveCopilotWorkspaceId } from "@/lib/copilot/scope";
import type { ProjectAgentPreset } from "@/features/projects/types";
import type { ProjectProgressResponse } from "@/lib/api";
import { useCopilotChat } from "@/lib/copilot/useCopilotChat";

export function ProjectRecapRail({
  open,
  onOpenChange,
  progress,
  preset,
  nextStep,
  onRecapChange,
  onAssistantUpdate,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  progress: ProjectProgressResponse;
  preset: ProjectAgentPreset;
  nextStep: string;
  onRecapChange: (recap: string | null) => void;
  onAssistantUpdate?: (recap: string) => void;
}) {
  const [helperDialogOpen, setHelperDialogOpen] = useState(false);
  const deliveredAssistantRef = useRef<string | null>(null);
  const { partner } = useAuth();
  const workspaceId = resolveCopilotWorkspaceId(partner);
  const entry = useMemo(
    () =>
      buildProjectRecapEntry({
        progress,
        preset,
        nextStep,
        workspaceId,
      }),
    [nextStep, preset, progress, workspaceId]
  );
  const {
    status,
    connectorStatus,
    messages,
    streamingText,
    capability,
    lastError,
    send,
    cancel,
    retry,
  } = useCopilotChat(entry);

  const latestAssistant = useMemo(
    () =>
      [...messages]
        .reverse()
        .find((message) => message.role === "assistant" && message.content.trim())
        ?.content ?? null,
    [messages]
  );
  const visibleMessages = useMemo(
    () => messages.filter((message) => message.role !== "system"),
    [messages]
  );
  const helperIssue = useMemo(() => {
    if (connectorStatus === "checking") return "正在檢查 helper";
    if (connectorStatus === "disconnected") return "helper 未連線";
    if (capability?.missingSkills?.length) {
      return `缺 skill：${capability.missingSkills.join("、")}`;
    }
    if (lastError) return lastError;
    return null;
  }, [capability?.missingSkills, connectorStatus, lastError]);
  const helperHealthy = connectorStatus === "connected" && !helperIssue;

  useEffect(() => {
    onRecapChange(latestAssistant);
  }, [latestAssistant, onRecapChange]);

  useEffect(() => {
    if (!latestAssistant) return;
    if (deliveredAssistantRef.current === latestAssistant) return;
    deliveredAssistantRef.current = latestAssistant;
    onAssistantUpdate?.(latestAssistant);
  }, [latestAssistant, onAssistantUpdate]);

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
          placeholder="直接問這個工作台的 milestone、plan、task、subtask、blocker 或下一步"
        />
      }
    >
      <div data-testid="project-recap-panel">
        <CopilotChatViewport
          messages={visibleMessages}
          streamingText={streamingText}
          isStreaming={status === "loading" || status === "streaming"}
          emptyStateTitle="Task Copilot"
          emptyStateDescription="直接開始問。"
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
