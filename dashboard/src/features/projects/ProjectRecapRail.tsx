"use client";

import { useEffect, useMemo, useState } from "react";
import { CopilotChatViewport } from "@/components/ai/CopilotChatViewport";
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
  const [showRawTranscript, setShowRawTranscript] = useState(false);
  const { partner } = useAuth();
  const entry = useMemo(
    () =>
      buildProjectRecapEntry({
        progress,
        preset,
        nextStep,
        workspaceId: resolveCopilotWorkspaceId(partner),
      }),
    [nextStep, partner, preset, progress]
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
  const rawTranscript = useMemo(
    () =>
      messages
        .map((message) => `[${message.role}] ${message.content}`.trim())
        .filter((line) => line.length > 0)
        .join("\n\n"),
    [messages]
  );
  const diagnostics = useMemo(() => {
    const issues: string[] = [];
    if (connectorStatus === "checking") issues.push("Connector 檢查中");
    if (connectorStatus === "disconnected") issues.push("Connector 未連線");
    capability?.missingSkills?.forEach((skill) => issues.push(`缺 skill：${skill}`));
    if (lastError) issues.push(lastError);
    return issues;
  }, [capability?.missingSkills, connectorStatus, lastError]);

  useEffect(() => {
    onRecapChange(latestAssistant);
  }, [latestAssistant, onRecapChange]);

  useEffect(() => {
    if (!latestAssistant) return;
    onAssistantUpdate?.(latestAssistant);
  }, [latestAssistant, onAssistantUpdate]);

  return (
    <CopilotRailShell
      open={open}
      onOpenChange={onOpenChange}
      entry={entry}
      chatStatus={status}
      connectorStatus={connectorStatus}
      inlineOnly
      diagnostics={
        diagnostics.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            {diagnostics.map((issue) => (
              <span key={issue}>{issue}</span>
            ))}
          </div>
        ) : undefined
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
          placeholder="直接問這個 product 的 milestone、plan、task、subtask、blocker 或下一步"
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
        {rawTranscript ? (
          <div className="mt-3 rounded-[2px] border bd-hair bg-panel">
            <button
              type="button"
              data-testid="project-raw-transcript-toggle"
              className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-dim"
              onClick={() => setShowRawTranscript((value) => !value)}
            >
              <span>Claude Code 原文</span>
              <span>{showRawTranscript ? "Hide" : "Show"}</span>
            </button>
            {showRawTranscript ? (
              <pre
                data-testid="project-raw-transcript"
                className="overflow-x-auto border-t bd-hair px-3 py-3 text-xs text-foreground"
                style={{ whiteSpace: "pre-wrap" }}
              >
                {rawTranscript}
                {streamingText ? `\n\n[assistant/streaming] ${streamingText}` : ""}
              </pre>
            ) : null}
          </div>
        ) : null}
      </div>
    </CopilotRailShell>
  );
}
