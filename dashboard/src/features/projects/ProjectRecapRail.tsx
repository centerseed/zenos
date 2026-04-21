"use client";

import { useEffect, useMemo } from "react";
import { CopilotChatViewport } from "@/components/ai/CopilotChatViewport";
import { CopilotInputBar } from "@/components/ai/CopilotInputBar";
import { CopilotRailShell } from "@/components/ai/CopilotRailShell";
import { buildProjectRecapEntry } from "@/features/projects/projectCopilot";
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
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  progress: ProjectProgressResponse;
  preset: ProjectAgentPreset;
  nextStep: string;
  onRecapChange: (recap: string | null) => void;
}) {
  const entry = useMemo(
    () => buildProjectRecapEntry({ progress, preset, nextStep }),
    [nextStep, preset, progress]
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

  useEffect(() => {
    onRecapChange(latestAssistant);
  }, [latestAssistant, onRecapChange]);

  return (
    <CopilotRailShell
      open={open}
      onOpenChange={onOpenChange}
      entry={entry}
      chatStatus={status}
      connectorStatus={connectorStatus}
      diagnostics={
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span>{connectorStatus === "connected" ? "Connector 已連線" : connectorStatus === "checking" ? "Connector 檢查中" : "Connector 未連線"}</span>
          {capability?.missingSkills?.map((skill) => (
            <span key={skill}>缺 skill：{skill}</span>
          ))}
          {lastError ? <span>{lastError}</span> : null}
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
          sendLabel={messages.length === 0 ? "產生 recap" : "續問"}
          placeholder="補充你要 AI 強調的決策點，或直接送出產生 recap"
        />
      }
    >
      <CopilotChatViewport
        messages={messages}
        streamingText={streamingText}
        isStreaming={status === "loading" || status === "streaming"}
        emptyStateTitle="Product Progress Recap"
        emptyStateDescription="產生一份可決策的 recap，整理 plans、blockers、下一步與待決策點。"
      />
    </CopilotRailShell>
  );
}
