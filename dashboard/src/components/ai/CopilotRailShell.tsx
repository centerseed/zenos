"use client";

import { useEffect, useState, type ReactNode } from "react";
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
  inlineOnly?: boolean;
  diagnostics?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

function useMinWidth(query: string) {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mediaQuery = window.matchMedia(query);
    const handleChange = () => setMatches(mediaQuery.matches);

    handleChange();
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, [query]);

  return matches;
}

export function CopilotRailShell({
  open,
  onOpenChange,
  entry,
  chatStatus,
  connectorStatus,
  desktopInline = false,
  inlineOnly = false,
  diagnostics,
  children,
  footer,
}: CopilotRailShellProps) {
  const isDesktopInlineViewport = useMinWidth("(min-width: 1280px)");
  const renderInlineShell = inlineOnly || (desktopInline && isDesktopInlineViewport);
  const renderSheetShell = !inlineOnly && (!desktopInline || !isDesktopInlineViewport);
  const inlineShellClass = inlineOnly
    ? "h-[min(76vh,840px)] md:h-[min(78vh,880px)] xl:h-[calc(100vh-7.5rem)] xl:max-h-[calc(100vh-7.5rem)]"
    : desktopInline
      ? "xl:h-[calc(100vh-7.5rem)] xl:max-h-[calc(100vh-7.5rem)]"
      : "";
  const shellContent = (
    <div
      className={`flex h-full flex-col overflow-hidden bg-background ${
        inlineOnly
          ? "rounded-[24px] border border-border/40 bg-card/80 shadow-[0_20px_50px_rgba(0,0,0,0.18)]"
          : desktopInline
            ? "xl:rounded-[28px] xl:border xl:border-border/40 xl:bg-card/80 xl:shadow-[0_28px_80px_rgba(0,0,0,0.2)]"
            : ""
      }`}
    >
      <div className="border-b border-border/40 px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-base font-medium text-foreground">{entry?.title || "AI 助手"}</h2>
            <p className="text-sm text-muted-foreground">{entry?.scope.scope_label || "尚未指定範圍"}</p>
          </div>
          <Badge variant="outline" className="text-[10px]">
            {statusText[chatStatus]}
          </Badge>
        </div>
        {diagnostics}
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer ? (
          <div className="max-h-[min(42vh,420px)] shrink-0 overflow-y-auto border-t border-border/30 bg-background px-4 py-4">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <>
      {renderInlineShell ? <div className={inlineShellClass}>{shellContent}</div> : null}
      {renderSheetShell ? (
        <Sheet open={open} onOpenChange={onOpenChange}>
          <SheetContent side="right" className="w-full overflow-hidden p-0 sm:max-w-3xl">
            {shellContent}
          </SheetContent>
        </Sheet>
      ) : null}
    </>
  );
}
