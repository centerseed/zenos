"use client";

import type { GraphContextResponse } from "@/lib/api";

function formatTags(tags: { what: string[]; why: string; who: string[] }): string {
  const parts = [
    tags.what.length > 0 ? tags.what.join(" / ") : "",
    tags.why,
    tags.who.length > 0 ? tags.who.join(" / ") : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

export function GraphContextBadge({
  graphContext,
  unavailableReason,
  className = "",
}: {
  graphContext: GraphContextResponse | null;
  unavailableReason?: string | null;
  className?: string;
}) {
  if (!graphContext) {
    if (!unavailableReason) return null;
    return (
      <div className={`rounded-xl border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 ${className}`.trim()}>
        {unavailableReason}
      </div>
    );
  }

  const l2Count = graphContext.neighbors.length;
  const l3Count = graphContext.neighbors.reduce((sum, neighbor) => sum + neighbor.documents.length, 0);
  const hiddenCount =
    (graphContext.truncation_details?.dropped_l2 || 0) + (graphContext.truncation_details?.dropped_l3 || 0);

  return (
    <details className={`rounded-xl border border-border/40 bg-card/60 px-3 py-2 text-xs text-muted-foreground ${className}`.trim()}>
      <summary className="cursor-pointer list-none font-medium text-foreground">
        已讀取 {l2Count} 個模組、{l3Count} 個文件 ▸
      </summary>
      <div className="mt-3 space-y-3">
        <div className="rounded-lg border border-border/30 bg-background/60 px-3 py-2">
          <div className="font-medium text-foreground">{graphContext.seed.name}</div>
          <div className="mt-1 text-[11px]">{formatTags(graphContext.seed.tags)}</div>
        </div>
        {graphContext.neighbors.map((neighbor) => (
          <div key={neighbor.id} className="rounded-lg border border-border/30 bg-background/50 px-3 py-2">
            <div className="font-medium text-foreground">
              {neighbor.name} <span className="text-[11px] text-muted-foreground">({neighbor.type})</span>
            </div>
            <div className="mt-1 text-[11px]">{formatTags(neighbor.tags)}</div>
            {neighbor.documents.length > 0 && (
              <div className="mt-2 space-y-1 border-t border-border/20 pt-2">
                {neighbor.documents.map((doc) => (
                  <div key={doc.id} className="text-[11px] text-muted-foreground">
                    {doc.title} <span className="text-[10px]">({doc.type} / {doc.status})</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {graphContext.truncated && hiddenCount > 0 && (
          <div className="rounded-lg border border-border/30 bg-background/50 px-3 py-2 text-[11px]">
            還有 {hiddenCount} 個節點因長度限制未載入
          </div>
        )}
      </div>
    </details>
  );
}

