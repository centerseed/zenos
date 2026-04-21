"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import type { CopilotChatStatus, CopilotEntryConfig } from "@/lib/copilot/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { Drawer } from "@/components/zen/Drawer";

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
  const t = useInk("light");
  const { c, fontBody, fontHead, fontMono } = t;
  const isDesktopInlineViewport = useMinWidth("(min-width: 1280px)");
  const renderInlineShell = inlineOnly || (desktopInline && isDesktopInlineViewport);
  const renderSheetShell = !inlineOnly && (!desktopInline || !isDesktopInlineViewport);
  const inlineShellClass = inlineOnly
    ? "h-[min(76vh,840px)] md:h-[min(78vh,880px)] xl:h-[calc(100vh-7.5rem)] xl:max-h-[calc(100vh-7.5rem)]"
    : desktopInline
      ? "xl:h-[calc(100vh-7.5rem)] xl:max-h-[calc(100vh-7.5rem)]"
      : "";
  const shellVars = {
    colorScheme: "light",
    fontFamily: fontBody,
    color: c.ink,
  } as CSSProperties;
  const statusTone =
    chatStatus === "error"
      ? c.vermillion
      : chatStatus === "apply-ready"
        ? c.jade
        : chatStatus === "streaming" || chatStatus === "loading" || chatStatus === "applying"
          ? c.ocher
          : c.inkMuted;
  const shellContent = (
    <div
      className={`flex h-full flex-col overflow-hidden bg-base ${
        inlineOnly
          ? "rounded-[2px] border bd-hair bg-panel shadow-[0_18px_40px_rgba(58,52,44,0.10)]"
          : desktopInline
            ? "xl:rounded-[2px] xl:border xl:bd-hair xl:bg-panel xl:shadow-[0_20px_44px_rgba(58,52,44,0.12)]"
            : ""
      }`}
      style={shellVars}
    >
      <div
        className="border-b bd-hair px-4 py-4"
        style={{
          background: c.surface,
          borderBottomColor: c.inkHair,
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2
              className="text-base text-foreground"
              style={{
                fontFamily: fontHead,
                fontWeight: 500,
                letterSpacing: "0.03em",
              }}
            >
              {entry?.title || "AI 助手"}
            </h2>
            <p
              className="text-sm text-dim"
              style={{
                marginTop: 2,
                color: c.inkMuted,
              }}
            >
              {entry?.scope.scope_label || "尚未指定範圍"}
            </p>
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 10px",
              borderRadius: 2,
              border: `1px solid ${statusTone === c.jade ? "rgba(95, 122, 69, 0.26)" : statusTone === c.vermillion ? "rgba(182, 58, 44, 0.24)" : c.inkHairBold}`,
              background:
                statusTone === c.jade
                  ? "rgba(95, 122, 69, 0.08)"
                  : statusTone === c.vermillion
                    ? "rgba(182, 58, 44, 0.08)"
                    : c.surfaceHi,
              color: statusTone,
              fontFamily: fontMono,
              fontSize: 10,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
          >
            {statusText[chatStatus]}
          </div>
        </div>
        {diagnostics ? (
          <div
            style={{
              marginTop: 14,
              paddingTop: 14,
              borderTop: `1px solid ${c.inkHair}`,
            }}
          >
            {diagnostics}
          </div>
        ) : null}
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div
          className="min-h-0 flex-1 overflow-y-auto px-4 py-4"
          style={{
            background: c.paperWarm,
          }}
        >
          {children}
        </div>
        {footer ? (
          <div
            className="max-h-[min(42vh,420px)] shrink-0 overflow-y-auto border-t bd-hair bg-base px-4 py-4"
            style={{
              background: c.surface,
              borderTopColor: c.inkHair,
            }}
          >
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
        <Drawer
          t={t}
          open={open}
          onOpenChange={onOpenChange}
          side="right"
          width="min(100vw, 48rem)"
        >
          {shellContent}
        </Drawer>
      ) : null}
    </>
  );
}
