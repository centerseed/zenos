"use client";

import { cn } from "@/lib/utils";

interface LoadingStateProps {
  label?: string;
  variant?: "page" | "inline" | "graph";
  className?: string;
}

export function LoadingState({
  label = "Loading",
  variant = "inline",
  className,
}: LoadingStateProps) {
  if (variant === "page") {
    return (
      <div className={cn("flex min-h-[50vh] items-center justify-center", className)}>
        <div className="flex flex-col items-center gap-3">
          <div className="h-9 w-9 rounded-full border-2 border-muted border-t-primary animate-spin" />
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </div>
    );
  }

  if (variant === "graph") {
    return (
      <div className={cn("w-full h-full rounded-xl border border-border bg-card p-4", className)}>
        <div className="h-full w-full rounded-lg bg-muted/30 animate-pulse flex items-center justify-center">
          <span className="text-sm text-muted-foreground">{label}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("inline-flex items-center gap-2", className)} role="status" aria-live="polite">
      <div className="h-4 w-4 rounded-full border-2 border-muted border-t-primary animate-spin" />
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}
