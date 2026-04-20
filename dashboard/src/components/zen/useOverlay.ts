// ZenOS · Zen Ink — useOverlay
// Native overlay helper: portal, z-index stacking, Esc close, click-outside, focus trap, focus restore
// SSR safe: portal only created in useEffect (Next.js 15 app router compatible)
"use client";

import { useEffect, useRef, useCallback } from "react";

export const Z = {
  overlay: 1000,
  drawer: 1001,
  dialog: 1002,
  tooltip: 1100,
  toast: 1200,
} as const;

// Selectable focusable elements inside a container
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => !el.closest("[aria-hidden='true']")
  );
}

interface UseOverlayOptions {
  open: boolean;
  onClose: () => void;
  /** Whether clicking the backdrop closes the overlay */
  closeOnClickOutside?: boolean;
  /** Whether Esc key closes the overlay */
  closeOnEsc?: boolean;
  /** Lock document.body scroll while open */
  lockBodyScroll?: boolean;
  /** Reference to the panel element (for focus trap) */
  panelRef: React.RefObject<HTMLElement | null>;
}

interface UseOverlayReturn {
  /** Call on the backdrop element's onClick */
  handleBackdropClick: (e: React.MouseEvent) => void;
  /** Ref to put on the first focusable element (or let trapFocus handle automatically) */
  trapFocus: (e: React.KeyboardEvent) => void;
}

export function useOverlay({
  open,
  onClose,
  closeOnClickOutside = true,
  closeOnEsc = true,
  lockBodyScroll = true,
  panelRef,
}: UseOverlayOptions): UseOverlayReturn {
  // Remember which element triggered the open so we can restore focus on close
  const triggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      // Remember current focus before we move it
      triggerRef.current = document.activeElement as HTMLElement;
    }
  }, [open]);

  // Focus first element in panel when opened
  useEffect(() => {
    if (!open) return;
    // Defer to allow the panel to render in the DOM first
    const id = requestAnimationFrame(() => {
      if (!panelRef.current) return;
      const focusable = getFocusableElements(panelRef.current);
      if (focusable.length > 0) {
        focusable[0].focus();
      } else {
        // If no focusable children, focus the panel itself
        panelRef.current.focus();
      }
    });
    return () => cancelAnimationFrame(id);
  }, [open, panelRef]);

  // Restore focus when closed
  useEffect(() => {
    if (!open && triggerRef.current) {
      const el = triggerRef.current;
      triggerRef.current = null;
      requestAnimationFrame(() => {
        if (el && typeof el.focus === "function") {
          el.focus();
        }
      });
    }
  }, [open]);

  // Global Esc handler
  useEffect(() => {
    if (!open || !closeOnEsc) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [open, closeOnEsc, onClose]);

  // Body scroll lock
  useEffect(() => {
    if (!lockBodyScroll || !open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open, lockBodyScroll]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (!closeOnClickOutside) return;
      // Only close if the click was directly on the backdrop, not a child
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [closeOnClickOutside, onClose]
  );

  // Tab / Shift+Tab trap within panel
  const trapFocus = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusable = getFocusableElements(panelRef.current);
      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (e.shiftKey) {
        // Shift+Tab: if at first, wrap to last
        if (active === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        // Tab: if at last, wrap to first
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [panelRef]
  );

  return { handleBackdropClick, trapFocus };
}

