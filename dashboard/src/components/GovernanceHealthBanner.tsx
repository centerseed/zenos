"use client";

import { useState, useCallback } from "react";

type HealthLevel = "green" | "yellow" | "red";

interface GovernanceHealthBannerProps {
  level: HealthLevel;
}

const COMMAND = "/zenos-governance";

export function GovernanceHealthBanner({ level }: GovernanceHealthBannerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(COMMAND);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available in all contexts
    }
  }, []);

  if (level === "green") return null;

  const isRed = level === "red";

  const bgClass = isRed
    ? "bg-red-500/10 border-red-500/20"
    : "bg-amber-500/10 border-amber-500/20";

  const textClass = isRed
    ? "text-red-400"
    : "text-amber-400";

  const message = isRed
    ? "知識地圖的品質可能正在影響 agent 的建議準確度"
    : "知識地圖有些內容可能需要整理";

  const guidance = isRed
    ? "建議儘快在 Claude Code 中執行"
    : "請在 Claude Code 中執行";

  const guidanceSuffix = isRed ? "" : " 進行自動治理";

  return (
    <div
      className={`mx-4 mt-3 rounded-lg border px-4 py-3 ${bgClass}`}
      role="status"
    >
      <p className={`text-sm font-medium ${textClass}`}>
        {message}
      </p>
      <p className="mt-1 text-xs text-dim">
        {guidance}{" "}
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded bg-foreground/5 px-1.5 py-0.5 font-mono text-xs text-foreground/80 hover:bg-foreground/10 transition-colors cursor-pointer"
          title="點擊複製指令"
        >
          {COMMAND}
        </button>
        {guidanceSuffix}
        {copied && (
          <span className="ml-2 text-emerald-400 text-xs">已複製</span>
        )}
      </p>
    </div>
  );
}
