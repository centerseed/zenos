// ZenOS · Zen Ink — Drawer (side panel shell)
// API: Designer spec §2.5
// Native implementation — no Radix. Focus trap, portal, ARIA, Esc, click-outside, body scroll lock.
// headerExtras slot: reserved for future Task L3 dispatcher badge / handoff timeline tabs
"use client";

import React, { useRef, useId, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { Z, useOverlay } from "./useOverlay";

export interface DrawerProps {
  t: ZenInkTokens;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: "right" | "left";
  width?: number | string;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
  /** At >=1280px render inline instead of overlay */
  desktopInline?: boolean;
  /** Extension point for Task L3: dispatcher badge / handoff timeline tabs in header */
  headerExtras?: React.ReactNode;
}

export function Drawer({
  t,
  open,
  onOpenChange,
  side = "right",
  width = 540,
  header,
  footer,
  children,
  desktopInline = false,
  headerExtras,
}: DrawerProps) {
  const { c, fontBody, fontMono } = t;
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const [mounted, setMounted] = useState(false);
  const [isInline, setIsInline] = useState(false);

  // SSR safe
  useEffect(() => {
    setMounted(true);
  }, []);

  // Desktop inline mode detection
  useEffect(() => {
    if (!desktopInline) return;
    const mq = window.matchMedia("(min-width: 1280px)");
    setIsInline(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsInline(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [desktopInline]);

  const handleClose = React.useCallback(() => onOpenChange(false), [onOpenChange]);

  const { handleBackdropClick, trapFocus } = useOverlay({
    open,
    onClose: handleClose,
    closeOnClickOutside: true,
    closeOnEsc: true,
    lockBodyScroll: !isInline,
    panelRef,
  });

  if (!mounted) return null;

  // Inline mode (no overlay)
  if (isInline) {
    return open ? (
      <aside
        ref={panelRef as React.RefObject<HTMLDivElement>}
        aria-label="側邊面板"
        style={{
          width,
          display: "flex",
          flexDirection: "column",
          background: c.surface,
          borderLeft: side === "right" ? `1px solid ${c.inkHair}` : undefined,
          borderRight: side === "left" ? `1px solid ${c.inkHair}` : undefined,
          height: "100%",
          overflow: "hidden",
        }}
      >
        {renderInner()}
      </aside>
    ) : null;
  }

  if (!open) return null;

  const slideDir = side === "right" ? "translateX(0)" : "translateX(0)";

  const content = (
    <div
      role="presentation"
      onClick={handleBackdropClick}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: Z.drawer,
        display: "flex",
        flexDirection: side === "right" ? "row-reverse" : "row",
        background: "rgba(20, 18, 16, 0.42)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={trapFocus}
        style={{
          position: "relative",
          width,
          maxWidth: "100vw",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: c.paper,
          borderLeft: side === "right" ? `1px solid ${c.inkHair}` : undefined,
          borderRight: side === "left" ? `1px solid ${c.inkHair}` : undefined,
          boxShadow:
            side === "right"
              ? "0 24px 60px rgba(58, 52, 44, 0.10)"
              : "0 24px 60px rgba(58, 52, 44, 0.10)",
          outline: "none",
          overflow: "hidden",
        }}
      >
        {renderInner()}
      </div>
    </div>
  );

  return createPortal(content, document.body);

  function renderInner() {
    return (
      <>
        {/* Header */}
        {(header || headerExtras) && (
          <div
            style={{
              background: c.surface,
              borderBottom: `1px solid ${c.inkHair}`,
              flexShrink: 0,
            }}
          >
            {header && (
              <div
                id={titleId}
                style={{ padding: "14px 20px" }}
              >
                {header}
              </div>
            )}
            {/* headerExtras: reserved for Task L3 dispatcher badge / handoff timeline tabs */}
            {headerExtras && (
              <div
                style={{
                  padding: "0 20px 10px",
                  borderTop: `1px solid ${c.inkHair}`,
                }}
              >
                {headerExtras}
              </div>
            )}
          </div>
        )}

        {/* Scrollable body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: 20,
          }}
        >
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              background: c.surface,
              borderTop: `1px solid ${c.inkHair}`,
              padding: "12px 20px",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {footer}
          </div>
        )}
      </>
    );
  }
}
