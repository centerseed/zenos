// ZenOS · Zen Ink — Toast (queue + auto-dismiss + a11y)
// API: Designer spec §2.10 minimal + Addendum §A3 native constraints.
// Native implementation — no Radix. Portal, queue, ARIA live region, Esc dismiss.
"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { ZenInkTokens, useInk } from "@/lib/zen-ink/tokens";
import { Z } from "./useOverlay";

// ---------- Types ----------

export type ToastTone = "success" | "error" | "info" | "warn";

export interface ToastInput {
  title: string;
  description?: string;
  tone: ToastTone;
  /** Auto-dismiss duration in ms (default 5000). `null` or `0` disables auto-dismiss. */
  duration?: number | null;
  /** Optional stable id (else auto-gen). */
  id?: string;
}

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  tone: ToastTone;
  /** Resolved duration: `null` = sticky; number = auto-dismiss ms */
  duration: number | null;
}

export interface ToastContextValue {
  showToast: (input: ToastInput) => string;
  pushToast: (input: Omit<ToastInput, "id">) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
}

// ---------- Context ----------

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      showToast: () => "",
      pushToast: () => "",
      dismiss: () => {},
      dismissAll: () => {},
    };
  }
  return ctx;
}

// ---------- Tone resolution ----------

interface ToneStyle {
  accent: string;
  role: "status" | "alert";
  ariaLive: "polite" | "assertive";
}

function resolveTone(tone: ToastTone, t: ZenInkTokens): ToneStyle {
  const { c } = t;
  switch (tone) {
    case "success":
      return { accent: c.jade, role: "status", ariaLive: "polite" };
    case "error":
      return { accent: c.vermillion, role: "alert", ariaLive: "assertive" };
    case "info":
      return { accent: c.inkMuted, role: "status", ariaLive: "polite" };
    case "warn":
      return { accent: c.ocher, role: "alert", ariaLive: "assertive" };
  }
}

// ---------- Default duration ----------

const DEFAULT_DURATION_MS = 5000;

function generateId(): string {
  // Prefer crypto.randomUUID; fall back to Math.random for older jsdom.
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `t_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

// ---------- Provider ----------

export interface ToastProviderProps {
  t?: ZenInkTokens;
  children: React.ReactNode;
}

export function ToastProvider({ t, children }: ToastProviderProps) {
  const resolvedTokens = t ?? useInk("light");
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [mounted, setMounted] = useState(false);
  const toastsRef = useRef<ToastItem[]>([]);
  toastsRef.current = toasts;

  // SSR safe — only mount portal after client hydration.
  useEffect(() => {
    setMounted(true);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setToasts([]);
  }, []);

  const showToast = useCallback((input: ToastInput): string => {
    const id = input.id ?? generateId();
    const duration =
      input.duration === undefined
        ? DEFAULT_DURATION_MS
        : input.duration === 0
          ? null
          : input.duration;
    const item: ToastItem = {
      id,
      title: input.title,
      description: input.description,
      tone: input.tone,
      duration,
    };
    setToasts((prev) => [...prev, item]);
    return id;
  }, []);

  // Esc dismisses the most recent toast
  useEffect(() => {
    if (toasts.length === 0) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const current = toastsRef.current;
      if (current.length === 0) return;
      const last = current[current.length - 1];
      e.preventDefault();
      dismiss(last.id);
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [toasts.length, dismiss]);

  const pushToast = useCallback((input: Omit<ToastInput, "id">) => showToast(input), [showToast]);

  const value = useMemo<ToastContextValue>(
    () => ({ showToast, pushToast, dismiss, dismissAll }),
    [showToast, pushToast, dismiss, dismissAll]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted &&
        createPortal(
          <ToastViewport t={resolvedTokens} toasts={toasts} onDismiss={dismiss} />,
          document.body
        )}
    </ToastContext.Provider>
  );
}

// ---------- Viewport (portal-rendered list) ----------

interface ToastViewportProps {
  t: ZenInkTokens;
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

function ToastViewport({ t, toasts, onDismiss }: ToastViewportProps) {
  return (
    <div
      aria-label="notifications"
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        zIndex: Z.toast,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        // Max viewport width so content never bleeds off-screen on narrow views
        maxWidth: "min(400px, calc(100vw - 40px))",
        pointerEvents: "none",
      }}
    >
      {toasts.map((toast) => (
        <ToastCard key={toast.id} t={t} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// ---------- Single toast card ----------

interface ToastCardProps {
  t: ZenInkTokens;
  toast: ToastItem;
  onDismiss: (id: string) => void;
}

function ToastCard({ t, toast, onDismiss }: ToastCardProps) {
  const { c, fontBody, fontHead, radius } = t;
  const { role, ariaLive, accent } = resolveTone(toast.tone, t);

  // Auto-dismiss timer (null = sticky, no timer)
  useEffect(() => {
    if (toast.duration === null) return;
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      role={role}
      aria-live={ariaLive}
      aria-atomic="true"
      style={{
        pointerEvents: "auto",
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        padding: "12px 14px",
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: radius,
        // Soft paper shadow — rgba, not hex (token system doesn't cover shadow alpha)
        boxShadow: "0 12px 32px rgba(58, 52, 44, 0.10)",
        fontFamily: fontBody,
        color: c.ink,
        minWidth: 260,
      }}
    >
      {/* Tone dot */}
      <span
        aria-hidden="true"
        style={{
          flexShrink: 0,
          marginTop: 6,
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: accent,
        }}
      />
      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: fontHead,
            fontSize: 13,
            fontWeight: 500,
            letterSpacing: "0.02em",
            color: c.ink,
            lineHeight: 1.35,
          }}
        >
          {toast.title}
        </div>
        {toast.description && (
          <div
            style={{
              marginTop: 4,
              fontFamily: fontBody,
              fontSize: 12,
              lineHeight: 1.5,
              color: c.inkMuted,
            }}
          >
            {toast.description}
          </div>
        )}
      </div>
      {/* Close button */}
      <button
        type="button"
        aria-label="關閉通知"
        onClick={() => onDismiss(toast.id)}
        style={{
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 22,
          height: 22,
          background: "transparent",
          border: "none",
          borderRadius: radius,
          cursor: "pointer",
          color: c.inkMuted,
          fontSize: 14,
          lineHeight: 1,
          transition: "background 0.15s, color 0.15s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = c.paperWarm;
          (e.currentTarget as HTMLButtonElement).style.color = c.ink;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          (e.currentTarget as HTMLButtonElement).style.color = c.inkMuted;
        }}
      >
        ✕
      </button>
    </div>
  );
}
