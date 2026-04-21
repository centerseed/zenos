"use client";

import { useState } from "react";
import { RefreshCw, Square, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { CopilotChatStatus } from "@/lib/copilot/types";
import type { ReactNode } from "react";

interface CopilotInputBarProps {
  status: CopilotChatStatus;
  onSend: (input: string) => void;
  onCancel: () => void;
  onRetry: () => void;
  onApply?: () => void;
  onSummarize?: () => void;
  hasStructuredResult: boolean;
  placeholder?: string;
  /** Label for the send button */
  sendLabel?: string;
  /** Allow sending with empty input (entry will build prompt from context) */
  canSendEmpty?: boolean;
  /** Extra slot for domain-specific buttons */
  extraActions?: ReactNode;
}

export function CopilotInputBar({
  status,
  onSend,
  onCancel,
  onRetry,
  onApply,
  onSummarize,
  hasStructuredResult,
  placeholder = "輸入訊息...",
  sendLabel,
  canSendEmpty = false,
  extraActions,
}: CopilotInputBarProps) {
  const [input, setInput] = useState("");
  const isRunning = status === "loading" || status === "streaming" || status === "applying";
  const isApplyReady = status === "apply-ready";

  function handleSend() {
    const trimmed = input.trim();
    if (isRunning) return;
    if (!trimmed && !canSendEmpty) return;
    setInput("");
    onSend(trimmed);
  }

  return (
    <div className="space-y-3">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          const nativeEvent = e.nativeEvent as KeyboardEvent & { isComposing?: boolean; keyCode?: number };
          if (nativeEvent.isComposing || nativeEvent.keyCode === 229) {
            return;
          }
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
          }
        }}
        placeholder={placeholder}
        disabled={isRunning}
        rows={3}
        className="w-full rounded-[2px] border border-border bg-card px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-primary/50 disabled:opacity-50"
      />
      <div className="flex flex-wrap items-center justify-end gap-2">
        {extraActions}

        {onSummarize && status === "idle" && (
          <Button size="sm" variant="outline" className="h-8 rounded-[2px] text-xs" onClick={onSummarize}>
            整理結果
          </Button>
        )}

        {status === "error" && (
          <Button size="sm" variant="outline" className="h-8 rounded-[2px] text-xs" onClick={onRetry}>
            <RefreshCw className="mr-1.5 h-3 w-3" />
            重試
          </Button>
        )}

        {isApplyReady && onApply && (
          <Button size="sm" className="h-8 rounded-[2px] text-xs" onClick={onApply}>
            套用到欄位
          </Button>
        )}

        {isRunning && (
          <Button size="sm" variant="outline" className="h-8 rounded-[2px] text-xs" onClick={onCancel}>
            <Square className="mr-1.5 h-3 w-3" />
            停止
          </Button>
        )}

        <Button
          size="sm"
          className="h-8 rounded-[2px] text-xs"
          disabled={isRunning || (!input.trim() && !canSendEmpty)}
          onClick={handleSend}
        >
          <Send className="mr-1.5 h-3 w-3" />
          {sendLabel ?? "送出"}
        </Button>
      </div>
    </div>
  );
}
