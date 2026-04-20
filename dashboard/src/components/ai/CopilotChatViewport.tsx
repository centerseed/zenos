"use client";

import { useEffect, useRef } from "react";
import { Bot } from "lucide-react";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import type { CopilotChatMessage } from "@/lib/copilot/useCopilotChat";

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
  const endRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom on new messages / streaming update
  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === "function") {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingText]);

  const hasContent = messages.length > 0 || streamingText;

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto rounded-[2px] border border-border/30 bg-card p-4">
      {!hasContent ? (
        // Empty state
        <div className="m-auto max-w-md text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-[2px] border border-border/30 bg-card">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div className="text-sm font-medium text-foreground">{emptyStateTitle}</div>
          <p className="mt-2 text-sm text-muted-foreground">{emptyStateDescription}</p>
        </div>
      ) : (
        <>
          {messages.map((msg, i) => (
            <div
              key={`${i}-${msg.timestamp}`}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "user" ? (
                <div className="max-w-[85%] rounded-[2px] border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-foreground">
                  {msg.content}
                </div>
              ) : msg.role === "assistant" ? (
                <div className="max-w-[85%] rounded-[2px] border border-border/30 bg-secondary/35 px-4 py-3 text-sm text-foreground">
                  <MarkdownRenderer content={msg.content} className="text-sm text-foreground space-y-1" />
                </div>
              ) : (
                // system
                <div className="max-w-[85%] rounded-[2px] border border-border/20 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                  {msg.content}
                </div>
              )}
            </div>
          ))}

          {/* Streaming bubble */}
          {isStreaming && streamingText && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-[2px] border border-border/30 bg-secondary/35 px-4 py-3 text-sm text-foreground">
                <MarkdownRenderer content={streamingText} className="text-sm text-foreground space-y-1" />
                <span className="ml-1 inline-block h-3 w-0.5 animate-pulse rounded-full bg-primary/60 align-middle" />
              </div>
            </div>
          )}

          <div ref={endRef} />
        </>
      )}
    </div>
  );
}
