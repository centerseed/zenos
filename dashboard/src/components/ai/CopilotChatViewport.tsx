"use client";

import { useEffect, useRef } from "react";
import { Bot } from "lucide-react";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import type { CopilotChatMessage } from "@/lib/copilot/useCopilotChat";
import { useInk } from "@/lib/zen-ink/tokens";

interface CopilotChatViewportProps {
  messages: CopilotChatMessage[];
  streamingText: string;
  isStreaming: boolean;
  emptyStateTitle?: string;
  emptyStateDescription?: string;
}

export function CopilotChatViewport({
  messages,
  streamingText,
  isStreaming,
  emptyStateTitle = "AI 助手準備就緒",
  emptyStateDescription = "輸入你的需求開始對話",
}: CopilotChatViewportProps) {
  const t = useInk("light");
  const { c } = t;
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "auto" });
  }, [messages, streamingText]);

  const hasContent = messages.length > 0 || streamingText;

  return (
    <div
      ref={viewportRef}
      className="flex h-full flex-col gap-3 overflow-y-auto rounded-[2px] border bd-hair bg-panel p-4"
    >
      {!hasContent ? (
        // Empty state
        <div className="m-auto max-w-md text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-[2px] border bd-hair bg-panel">
            <Bot className="h-5 w-5" style={{ color: c.vermillion }} />
          </div>
          <div className="text-sm font-medium text-foreground">{emptyStateTitle}</div>
          <p className="mt-2 text-sm text-dim">{emptyStateDescription}</p>
        </div>
      ) : (
        <>
          {messages.map((msg, i) => (
            <div
              key={`${i}-${msg.timestamp}`}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "user" ? (
                <div
                  className="max-w-[85%] rounded-[2px] px-4 py-3 text-sm text-foreground"
                  style={{
                    border: `1px solid ${c.vermLine}`,
                    background: c.vermSoft,
                  }}
                >
                  {msg.content}
                </div>
              ) : msg.role === "assistant" ? (
                <div className="max-w-[85%] rounded-[2px] border bd-hair bg-soft px-4 py-3 text-sm text-foreground">
                  <MarkdownRenderer content={msg.content} className="text-sm text-foreground space-y-1" />
                </div>
              ) : (
                // system
                <div className="max-w-[85%] rounded-[2px] border bd-hair bg-muted/20 px-3 py-2 text-xs text-dim">
                  {msg.content}
                </div>
              )}
            </div>
          ))}

          {/* Streaming bubble */}
          {isStreaming && streamingText && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-[2px] border bd-hair bg-soft px-4 py-3 text-sm text-foreground">
                <MarkdownRenderer content={streamingText} className="text-sm text-foreground space-y-1" />
                <span
                  className="ml-1 inline-block h-3 w-0.5 animate-pulse rounded-full align-middle"
                  style={{ background: c.vermillion }}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
