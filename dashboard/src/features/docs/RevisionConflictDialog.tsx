"use client";

import React, { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Dialog } from "@/components/zen/Dialog";
import { Btn } from "@/components/zen/Btn";

export interface RevisionConflictInfo {
  current_revision_id: string;
  canonical_path?: string;
  localContent: string;
}

interface RevisionConflictDialogProps {
  open: boolean;
  info: RevisionConflictInfo | null;
  /** Reload latest revision — discards local content */
  onReload: () => void;
  /** Copy local content to clipboard then reload */
  onCopyAndReload: () => void;
}

export function RevisionConflictDialog({
  open,
  info,
  onReload,
  onCopyAndReload,
}: RevisionConflictDialogProps) {
  const t = useInk();
  const { c, fontBody, fontMono } = t;
  const [copied, setCopied] = useState(false);

  if (!info) return null;

  async function handleCopyAndReload() {
    try {
      await navigator.clipboard.writeText(info!.localContent);
      setCopied(true);
    } catch {
      // clipboard API may fail in non-secure context; fall back to no-op
    }
    setTimeout(() => {
      setCopied(false);
      onCopyAndReload();
    }, 800);
  }

  return (
    <Dialog
      t={t}
      open={open}
      onOpenChange={() => {
        // intentionally non-closable except via action buttons
      }}
      closable={false}
      title="文件版本衝突"
      description="有人在你編輯期間更新了這份文件。你的版本是基於舊的 revision，無法直接儲存。"
      size="sm"
      footer={
        <>
          <span data-testid="copy-local-btn">
            <Btn
              t={t}
              variant="ghost"
              size="sm"
              onClick={handleCopyAndReload}
            >
              {copied ? "已複製，正在載入…" : "複製我的內容，再載入最新版"}
            </Btn>
          </span>
          <span data-testid="reload-latest-btn">
            <Btn
              t={t}
              variant="seal"
              size="sm"
              onClick={onReload}
            >
              載入最新版（丟棄本地改動）
            </Btn>
          </span>
        </>
      }
    >
      <div>
        <div
          style={{
            padding: "10px 12px",
            background: c.vermSoft,
            border: `1px solid ${c.vermLine}`,
            borderRadius: 2,
            fontSize: 12,
            color: c.ink,
            fontFamily: fontBody,
            lineHeight: 1.7,
          }}
        >
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.vermillion, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
            衝突詳情
          </div>
          <div>伺服器最新 revision：</div>
          <div style={{ fontFamily: fontMono, fontSize: 11, color: c.inkSoft, marginTop: 2 }}>
            {info.current_revision_id.slice(0, 16)}…
          </div>
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: c.inkMuted, fontFamily: fontBody, lineHeight: 1.6 }}>
          請選擇：
          <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
            <li><b>載入最新版</b>：丟棄本地未儲存的改動，改以伺服器版本繼續編輯。</li>
            <li style={{ marginTop: 4 }}><b>複製我的內容</b>：把你的編輯複製到剪貼板，再載入最新版，手動 merge。</li>
          </ul>
        </div>
      </div>
    </Dialog>
  );
}
