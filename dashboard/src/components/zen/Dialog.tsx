// ZenOS · Zen Ink — Dialog (modal shell)
// API: Designer spec §2.6
// Native implementation — no Radix. Focus trap, portal, ARIA, Esc, click-outside, body scroll lock.
"use client";

import React, { useRef, useId, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { Z, useOverlay } from "./useOverlay";

type DialogSize = "sm" | "md" | "lg";

const sizeWidths: Record<DialogSize, number> = {
  sm: 400,
  md: 520,
  lg: 720,
};

export interface DialogProps {
  t: ZenInkTokens;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  size?: DialogSize;
  children: React.ReactNode;
  footer?: React.ReactNode;
  closable?: boolean;
}

export function Dialog({
  t,
  open,
  onOpenChange,
  title,
  description,
  size = "md",
  children,
  footer,
  closable = true,
}: DialogProps) {
  const { c, fontHead, fontBody, fontMono, radius } = t;
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();
  const [mounted, setMounted] = useState(false);

  // SSR safe — only mount portal after client hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  const handleClose = React.useCallback(() => {
    if (closable) onOpenChange(false);
  }, [closable, onOpenChange]);

  const { handleBackdropClick, trapFocus } = useOverlay({
    open,
    onClose: handleClose,
    closeOnClickOutside: closable,
    closeOnEsc: closable,
    lockBodyScroll: true,
    panelRef,
  });

  if (!mounted || !open) return null;

  const width = sizeWidths[size];

  const content = (
    <div
      role="presentation"
      onClick={handleBackdropClick}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: Z.dialog,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(20, 18, 16, 0.42)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        padding: 24,
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onKeyDown={trapFocus}
        style={{
          position: "relative",
          width,
          maxWidth: "100%",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: radius,
          boxShadow: "0 24px 60px rgba(58, 52, 44, 0.10)",
          outline: "none",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        {(title || closable) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 20px",
              background: c.surface,
              borderBottom: `1px solid ${c.inkHair}`,
              flexShrink: 0,
            }}
          >
            {title && (
              <h2
                id={titleId}
                style={{
                  margin: 0,
                  fontFamily: fontHead,
                  fontSize: 16,
                  fontWeight: 500,
                  letterSpacing: "0.02em",
                  color: c.ink,
                  lineHeight: 1.3,
                }}
              >
                {title}
              </h2>
            )}
            {closable && (
              <button
                type="button"
                aria-label="關閉"
                onClick={handleClose}
                style={{
                  marginLeft: "auto",
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 28,
                  height: 28,
                  background: "transparent",
                  border: "none",
                  borderRadius: radius,
                  cursor: "pointer",
                  color: c.inkMuted,
                  fontSize: 16,
                  lineHeight: 1,
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) =>
                  ((e.currentTarget as HTMLButtonElement).style.background = c.paperWarm)
                }
                onMouseLeave={(e) =>
                  ((e.currentTarget as HTMLButtonElement).style.background = "transparent")
                }
              >
                ✕
              </button>
            )}
          </div>
        )}

        {/* Body */}
        <div
          style={{
            padding: "20px",
            overflowY: "auto",
            flex: 1,
          }}
        >
          {description && (
            <p
              id={descId}
              style={{
                margin: "0 0 16px",
                fontFamily: fontBody,
                fontSize: 13,
                lineHeight: 1.6,
                color: c.inkMuted,
              }}
            >
              {description}
            </p>
          )}
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 8,
              padding: "12px 20px",
              background: c.surface,
              borderTop: `1px solid ${c.inkHair}`,
              flexShrink: 0,
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
