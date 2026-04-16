"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
} from "@/components/ui/sheet";
import type { CopilotChatStatus, CopilotEntryConfig } from "@/lib/copilot/types";

type ConnectorStatus = "checking" | "connected" | "disconnected";

const statusText: Record<CopilotChatStatus, string> = {
  idle: "等待輸入",
  loading: "初始化中",
  streaming: "AI 回覆中",
  "awaiting-local-approval": "等待本機確認",
  "apply-ready": "可套用",
  applying: "寫回中",
  error: "需要修復",
};

const connectorText: Record<ConnectorStatus, string> = {
  checking: "Connector 檢查中",
  connected: "Connector 已連線",
  disconnected: "Connector 未連線",
};

export interface CopilotRailShellProps {
  open: boolean;
  onOpenChange: (nextOpen: boolean) => void;
  entry: CopilotEntryConfig | null;
  chatStatus: CopilotChatStatus;
  connectorStatus: ConnectorStatus;
  desktopInline?: boolean;
  diagnostics?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

export function CopilotRailShell({
  open,
  onOpenChange,
  entry,
  chatStatus,
  connectorStatus,
  desktopInline = false,
  diagnostics,
  children,
  footer,
}: CopilotRailShellProps) {
  const shellContent = (
    <div
      className={`flex h-full flex-col overflow-hidden bg-background ${
        desktopInline ? "xl:rounded-[28px] xl:border xl:border-border/40 xl:bg-card/80 xl:shadow-[0_28px_80px_rgba(0,0,0,0.2)]" : ""
      }`}
    >
      <div className="border-b border-border/40 px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-base font-medium text-foreground">{entry?.title || "AI 助手"}</h2>
            <p className="text-sm text-muted-foreground">{entry?.scope.scope_label || "尚未指定範圍"}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="text-[10px]">
              {statusText[chatStatus]}
            </Badge>
            <Badge variant="outline" className="text-[10px]">
              {connectorText[connectorStatus]}
            </Badge>
            {entry?.mode && (
              <Badge variant="outline" className="text-[10px]">
                mode {entry.mode}
              </Badge>
            )}
          </div>
        </div>
        {diagnostics}
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer ? <div className="border-t border-border/30 bg-background px-4 py-4">{footer}</div> : null}
      </div>
    </div>
  );

  return (
    <>
      {desktopInline ? <div className="hidden xl:block">{shellContent}</div> : null}
      <div className={desktopInline ? "xl:hidden" : undefined}>
        <Sheet open={open} onOpenChange={onOpenChange}>
          <SheetContent side="right" className="w-full overflow-hidden p-0 sm:max-w-3xl">
            {shellContent}
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
