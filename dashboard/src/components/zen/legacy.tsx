"use client";

import React, { createContext, useContext, useId, useMemo, useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Btn } from "./Btn";
import { Chip } from "./Chip";
import { Drawer } from "./Drawer";

type ButtonVariant = "default" | "outline" | "ghost";
type ButtonSize = "sm" | "icon-sm";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  render?: React.ReactElement;
}

function mapButtonVariant(variant: ButtonVariant) {
  if (variant === "outline") return "outline";
  if (variant === "ghost") return "ghost";
  return "seal";
}

export function Button({
  variant = "default",
  size = "sm",
  className,
  render,
  children,
  onClick,
  disabled,
  type,
  ...props
}: ButtonProps) {
  const t = useInk("light");
  const buttonEl = (
    <Btn
      t={t}
      variant={mapButtonVariant(variant)}
      size="sm"
      onClick={onClick ? () => onClick({} as React.MouseEvent<HTMLButtonElement>) : undefined}
      disabled={disabled}
      style={size === "icon-sm" ? { width: 28, height: 28, padding: 0 } : undefined}
    >
      {children}
    </Btn>
  );

  if (!render) {
    return buttonEl;
  }

  return React.cloneElement(render as React.ReactElement<Record<string, unknown>>, {
    ...props,
    type,
    onClick,
    disabled,
    className,
    children,
  });
}

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "outline" | "secondary" | "ghost";
}

export function Badge({ variant = "default", className, children, ...props }: BadgeProps) {
  const t = useInk("light");
  const tone = variant === "outline" ? "plain" : variant === "secondary" ? "muted" : "accent";
  return (
    <span className={className} {...props}>
      <Chip t={t} tone={tone}>
        {children}
      </Chip>
    </span>
  );
}

type SheetContextValue = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

const SheetContext = createContext<SheetContextValue | null>(null);

function useSheetContext() {
  const ctx = useContext(SheetContext);
  if (!ctx) throw new Error("Sheet components must be used within <Sheet>");
  return ctx;
}

interface SheetProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  modal?: boolean;
}

export function Sheet({ open, onOpenChange, children }: SheetProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const actualOpen = open ?? internalOpen;
  const setOpen = (next: boolean) => {
    if (open === undefined) setInternalOpen(next);
    onOpenChange?.(next);
  };
  const value = useMemo(() => ({ open: actualOpen, setOpen }), [actualOpen]);
  return <SheetContext.Provider value={value}>{children}</SheetContext.Provider>;
}

interface SheetTriggerProps {
  children?: React.ReactNode;
  render?: React.ReactElement;
}

export function SheetTrigger({ children, render }: SheetTriggerProps) {
  const { setOpen } = useSheetContext();
  if (render) {
    return React.cloneElement(render as React.ReactElement<Record<string, unknown>>, {
      onClick: () => setOpen(true),
    });
  }
  return <button onClick={() => setOpen(true)}>{children}</button>;
}

export function SheetClose({ children }: { children?: React.ReactNode }) {
  const { setOpen } = useSheetContext();
  return <button onClick={() => setOpen(false)}>{children}</button>;
}

interface SheetContentProps {
  children: React.ReactNode;
  side?: "right" | "left";
  className?: string;
  showOverlay?: boolean;
}

export function SheetContent({ children, side = "right" }: SheetContentProps) {
  const { open, setOpen } = useSheetContext();
  const t = useInk("light");
  return (
    <Drawer
      t={t}
      open={open}
      onOpenChange={setOpen}
      side={side}
      width={540}
    >
      {children}
    </Drawer>
  );
}

export function SheetHeader({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className}>{children}</div>;
}

export function SheetFooter({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className}>{children}</div>;
}

export function SheetTitle({ className, children }: React.HTMLAttributes<HTMLHeadingElement>) {
  const id = useId();
  return (
    <h2 id={id} className={className}>
      {children}
    </h2>
  );
}

export function SheetDescription({ className, children }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={className}>{children}</p>;
}
