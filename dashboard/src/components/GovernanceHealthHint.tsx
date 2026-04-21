"use client";

import { useState, useCallback } from "react";

type HealthLevel = "green" | "yellow" | "red";

const COMMAND = "/zenos-governance";

export function GovernanceHealthHint({ level }: { level: HealthLevel }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(COMMAND);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available
    }
  }, []);

  if (level === "green") return null;

  const isRed = level === "red";

  return (
    <div className="mt-2">
      <p className={`text-[10px] leading-tight ${isRed ? "text-red-400/80" : "text-amber-400/80"}`}>
        {isRed
          ? "品質可能影響 agent 建議"
          : "有些內容可能需要整理"}
      </p>
      <p className="mt-0.5 text-[10px] text-dim leading-tight">
        <button
          onClick={handleCopy}
          className="inline rounded bg-foreground/5 px-1 py-px font-mono text-[10px] text-foreground/60 hover:bg-foreground/10 transition-colors cursor-pointer"
          title="點擊複製指令"
        >
          {COMMAND}
        </button>
        {copied && <span className="ml-1 text-emerald-400">copied</span>}
      </p>
    </div>
  );
}
