"use client";

import type { StructuredResult } from "@/lib/copilot/types";

interface ChangePreviewItem {
  label: string;
  before: string;
  after: string;
}

interface CopilotApplyPreviewProps {
  result: StructuredResult;
  changePreview?: ChangePreviewItem[];
  missingKeys?: string[];
}

export function CopilotApplyPreview({
  result,
  changePreview,
  missingKeys,
}: CopilotApplyPreviewProps) {
  return (
    <div className="rounded-zen border border-emerald-500/20 bg-emerald-500/5 p-3">
      <div className="mb-2 text-xs font-medium text-foreground">
        可套用變更：{result.summary ?? result.target}
      </div>

      {missingKeys && missingKeys.length > 0 && (
        <div className="mb-2 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          結構化結果缺少鍵：{missingKeys.join(", ")}
        </div>
      )}

      {changePreview && changePreview.length > 0 && (
        <div className="mb-3 grid gap-2">
          {changePreview.map((item) => (
            <div key={item.label} className="rounded-md border bd-hair bg-base p-2">
              <div className="mb-2 text-[11px] font-medium text-foreground">{item.label}</div>
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <div className="mb-1 text-[10px] uppercase tracking-wide text-dim">目前</div>
                  <div className="whitespace-pre-wrap rounded border bd-hair bg-panel px-2 py-1.5 text-[11px] text-dim">
                    {item.before}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[10px] uppercase tracking-wide text-dim">套用後</div>
                  <div className="whitespace-pre-wrap rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1.5 text-[11px] text-foreground">
                    {item.after}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] text-dim">
        {typeof result.value === "string" ? result.value : JSON.stringify(result.value, null, 2)}
      </pre>
    </div>
  );
}
