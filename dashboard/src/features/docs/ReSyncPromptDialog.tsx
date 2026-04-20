"use client";

import React, { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Dialog } from "@/components/zen/Dialog";
import { Btn } from "@/components/zen/Btn";
import type { DocSource } from "./DocSourceList";

interface ReSyncPromptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: DocSource | null;
}

function buildHelperPrompt(source: DocSource): string {
  const sourceType = source.type; // e.g. "notion", "gdrive"
  const mcpName = sourceType === "notion" ? "Notion MCP" : sourceType === "gdrive" ? "Google Drive MCP" : "對應 MCP";
  const lines = [
    `請用 ${mcpName} 讀取 ${source.uri} 的最新內容，`,
    `然後用 ZenOS MCP 的 write(update_source) 更新 source_id=${source.source_id ?? "(unknown)"}` +
      (source.external_id ? `（external_id=${source.external_id}）` : "") +
      "。",
  ];
  return lines.join("\n");
}

export function ReSyncPromptDialog({ open, onOpenChange, source }: ReSyncPromptDialogProps) {
  const t = useInk();
  const { c, fontMono, fontBody } = t;
  const [copied, setCopied] = useState(false);

  if (!source) return null;

  const prompt = buildHelperPrompt(source);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: select textarea content
    }
  }

  return (
    <Dialog
      t={t}
      open={open}
      onOpenChange={onOpenChange}
      title="重新同步來源"
      description="複製以下 Helper prompt，在 Claude Desktop（或其他 MCP client）執行即可更新此來源。"
      size="md"
      footer={
        <>
          <Btn t={t} variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            關閉
          </Btn>
          <span data-testid="copy-prompt-btn">
            <Btn
              t={t}
              variant="ink"
              size="sm"
              onClick={handleCopy}
            >
              {copied ? "已複製" : "複製 Prompt"}
            </Btn>
          </span>
        </>
      }
    >
      <div>
        {/* Source info */}
        <div style={{ marginBottom: 12, fontSize: 12, color: c.inkMuted, fontFamily: fontBody }}>
          <span style={{ color: c.inkFaint, fontFamily: fontMono, fontSize: 10, marginRight: 6 }}>來源</span>
          {source.label || source.uri}
          {source.source_id && (
            <span style={{ marginLeft: 8, fontFamily: fontMono, fontSize: 10, color: c.inkFaint }}>
              #{source.source_id.slice(0, 8)}
            </span>
          )}
        </div>

        {/* Prompt textarea */}
        <textarea
          data-testid="helper-prompt-text"
          readOnly
          value={prompt}
          onClick={(e) => (e.target as HTMLTextAreaElement).select()}
          style={{
            width: "100%",
            minHeight: 100,
            padding: "12px 14px",
            background: c.paperWarm,
            border: `1px solid ${c.inkHair}`,
            borderRadius: 2,
            fontFamily: fontMono,
            fontSize: 12,
            color: c.ink,
            lineHeight: 1.7,
            resize: "vertical",
            outline: "none",
            boxSizing: "border-box",
          }}
        />

        <div style={{ marginTop: 8, fontSize: 11, color: c.inkFaint, fontFamily: fontBody }}>
          ZenOS server 不會主動抓取外部文件。請在你的 MCP client 執行此 prompt。
        </div>
      </div>
    </Dialog>
  );
}
