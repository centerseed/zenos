// ZenOS · Zen Ink — Tooltip
// API: Designer spec §2.10
// Native implementation — no Radix. Portal, hover+focus trigger, Esc close, role=tooltip, aria-describedby.
"use client";

import React, {
  useState,
  useRef,
  useEffect,
  useId,
  useCallback,
  cloneElement,
  isValidElement,
} from "react";
import { createPortal } from "react-dom";
import { ZenInkTokens } from "@/lib/zen-ink/tokens";
import { Z } from "./useOverlay";

export interface TooltipProps {
  t: ZenInkTokens;
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  /** Delay before showing in ms */
  delay?: number;
}

export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

type Side = "top" | "bottom" | "left" | "right";

function computePosition(
  rect: DOMRect,
  side: Side,
  tooltipW: number,
  tooltipH: number
): { top: number; left: number } {
  const scrollY = window.scrollY;
  const scrollX = window.scrollX;
  const gap = 8;

  switch (side) {
    case "top":
      return {
        top: rect.top + scrollY - tooltipH - gap,
        left: rect.left + scrollX + rect.width / 2 - tooltipW / 2,
      };
    case "bottom":
      return {
        top: rect.bottom + scrollY + gap,
        left: rect.left + scrollX + rect.width / 2 - tooltipW / 2,
      };
    case "left":
      return {
        top: rect.top + scrollY + rect.height / 2 - tooltipH / 2,
        left: rect.left + scrollX - tooltipW - gap,
      };
    case "right":
      return {
        top: rect.top + scrollY + rect.height / 2 - tooltipH / 2,
        left: rect.right + scrollX + gap,
      };
  }
}

export function Tooltip({
  t,
  content,
  children,
  side = "top",
  delay = 300,
}: TooltipProps) {
  const { c, fontBody, fontMono, radius } = t;
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [mounted, setMounted] = useState(false);
  const tooltipId = useId();
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const showTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const hideTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    setMounted(true);
    return () => {
      clearTimeout(showTimer.current);
      clearTimeout(hideTimer.current);
    };
  }, []);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const { offsetWidth: w, offsetHeight: h } = tooltipRef.current;
    setPosition(computePosition(rect, side, w, h));
  }, [side]);

  const show = useCallback(() => {
    clearTimeout(hideTimer.current);
    showTimer.current = setTimeout(() => {
      setVisible(true);
      // Wait for render then position
      requestAnimationFrame(updatePosition);
    }, delay);
  }, [delay, updatePosition]);

  const hide = useCallback(() => {
    clearTimeout(showTimer.current);
    hideTimer.current = setTimeout(() => setVisible(false), 80);
  }, []);

  // Esc closes
  useEffect(() => {
    if (!visible) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setVisible(false);
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [visible]);

  // Clone child to attach event handlers and aria-describedby
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type AnyProps = Record<string, any>;

  const child = React.Children.only(children);
  const trigger = isValidElement(child)
    ? cloneElement(child as React.ReactElement<AnyProps>, {
        ref: triggerRef,
        "aria-describedby": visible ? tooltipId : undefined,
        onMouseEnter: (e: React.MouseEvent) => {
          show();
          (child.props as AnyProps).onMouseEnter?.(e);
        },
        onMouseLeave: (e: React.MouseEvent) => {
          hide();
          (child.props as AnyProps).onMouseLeave?.(e);
        },
        onFocus: (e: React.FocusEvent) => {
          show();
          (child.props as AnyProps).onFocus?.(e);
        },
        onBlur: (e: React.FocusEvent) => {
          hide();
          (child.props as AnyProps).onBlur?.(e);
        },
      })
    : child;

  const tooltipEl = mounted && visible && (
    <div
      ref={tooltipRef}
      id={tooltipId}
      role="tooltip"
      style={{
        position: "absolute",
        top: position.top,
        left: position.left,
        zIndex: Z.tooltip,
        background: c.ink,
        color: c.paper,
        fontFamily: fontBody,
        fontSize: 11,
        lineHeight: 1.5,
        letterSpacing: "0.01em",
        padding: "5px 9px",
        borderRadius: radius,
        boxShadow: "0 4px 12px rgba(20, 18, 16, 0.18)",
        whiteSpace: "nowrap",
        maxWidth: 240,
        pointerEvents: "none",
      }}
    >
      {content}
    </div>
  );

  return (
    <>
      {trigger}
      {tooltipEl && createPortal(tooltipEl, document.body)}
    </>
  );
}
