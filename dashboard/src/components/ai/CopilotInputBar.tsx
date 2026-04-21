"use client";

import { useState } from "react";
import type { CopilotChatStatus } from "@/lib/copilot/types";
import type { ReactNode } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Btn } from "@/components/zen/Btn";
import { Textarea } from "@/components/zen/Textarea";

interface CopilotInputBarProps {
  status: CopilotChatStatus;
  onSend: (input: string) => void;
  onCancel: () => void;
  onRetry: () => void;
  onApply?: () => void;
  onSummarize?: () => void;
  hasStructuredResult: boolean;
  placeholder?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  /** Label for the send button */
  sendLabel?: string;
  /** When false, Enter requires Ctrl/Cmd to send */
  sendOnPlainEnter?: boolean;
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
  value,
  onValueChange,
  sendLabel,
  sendOnPlainEnter = true,
  canSendEmpty = false,
  extraActions,
}: CopilotInputBarProps) {
  const t = useInk("light");
  const [internalInput, setInternalInput] = useState("");
  const input = value ?? internalInput;
  const setInput = onValueChange ?? setInternalInput;
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
      <Textarea
        t={t}
        value={input}
        onChange={setInput}
        onKeyDown={(e) => {
          const nativeEvent = e.nativeEvent as KeyboardEvent & { isComposing?: boolean; keyCode?: number };
          if (nativeEvent.isComposing || nativeEvent.keyCode === 229) {
            return;
          }
          if (e.key !== "Enter" || e.shiftKey) {
            return;
          }
          const wantsModifier = e.metaKey || e.ctrlKey;
          if (sendOnPlainEnter || wantsModifier) {
            e.preventDefault();
            handleSend();
          }
        }}
        placeholder={placeholder}
        disabled={isRunning}
        rows={3}
        resize="vertical"
      />
      <div className="flex flex-wrap items-center justify-end gap-2">
        {extraActions}

        {onSummarize && status === "idle" && (
          <Btn t={t} size="sm" variant="outline" onClick={onSummarize}>
            整理結果
          </Btn>
        )}

        {status === "error" && (
          <Btn t={t} size="sm" variant="outline" onClick={onRetry}>
            重試
          </Btn>
        )}

        {isApplyReady && onApply && (
          <Btn t={t} size="sm" variant="ink" onClick={onApply}>
            套用到欄位
          </Btn>
        )}

        {isRunning && (
          <Btn t={t} size="sm" variant="outline" onClick={onCancel}>
            停止
          </Btn>
        )}

        <Btn
          t={t}
          size="sm"
          variant="ink"
          disabled={isRunning || (!input.trim() && !canSendEmpty)}
          onClick={handleSend}
        >
          {sendLabel ?? "送出"}
        </Btn>
      </div>
    </div>
  );
}
