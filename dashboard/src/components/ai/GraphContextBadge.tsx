"use client";

import type { GraphContextResponse } from "@/lib/api";
import { useInk } from "@/lib/zen-ink/tokens";

function formatTags(tags: { what: string[]; why: string; who: string[] }): string {
  const parts = [
    tags.what.length > 0 ? tags.what.join(" / ") : "",
    tags.why,
    tags.who.length > 0 ? tags.who.join(" / ") : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function compactText(value: string, max = 88): string {
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

export function GraphContextBadge({
  graphContext,
  unavailableReason,
  className = "",
  compact = false,
}: {
  graphContext: GraphContextResponse | null;
  unavailableReason?: string | null;
  className?: string;
  compact?: boolean;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;

  if (!graphContext) {
    if (!unavailableReason) return null;
    return (
      <div
        className={className}
        style={{
          borderRadius: 2,
          border: `1px solid ${c.vermLine}`,
          background: c.vermSoft,
          color: c.ink,
          padding: "10px 12px",
          fontSize: 12,
          lineHeight: 1.55,
        }}
      >
        {unavailableReason}
      </div>
    );
  }

  const l2Count = graphContext.neighbors.length;
  const l3Count = graphContext.neighbors.reduce((sum, neighbor) => sum + neighbor.documents.length, 0);
  const hiddenCount =
    (graphContext.truncation_details?.dropped_l2 || 0) + (graphContext.truncation_details?.dropped_l3 || 0);

  return (
    <details
      className={className}
      style={{
        borderRadius: 2,
        border: `1px solid ${c.inkHair}`,
        background: c.surface,
        padding: "10px 12px",
        color: c.inkMuted,
        fontSize: 12,
      }}
    >
      <summary
        className="cursor-pointer list-none"
        style={{
          color: c.ink,
          fontFamily: fontMono,
          fontSize: 11,
          letterSpacing: "0.08em",
        }}
      >
        已讀取 {l2Count} 個模組、{l3Count} 個文件 ▸
      </summary>
      <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
        <div
          style={{
            borderRadius: 2,
            border: `1px solid ${c.inkHair}`,
            background: c.paperWarm,
            padding: "10px 12px",
          }}
        >
          <div style={{ fontWeight: 600, color: c.ink }}>{graphContext.seed.name}</div>
          <div style={{ marginTop: 4, fontSize: 11, lineHeight: 1.55 }}>
            {compact ? compactText(formatTags(graphContext.seed.tags), 96) : formatTags(graphContext.seed.tags)}
          </div>
        </div>
        {graphContext.neighbors.map((neighbor) =>
          compact ? (
            <div
              key={neighbor.id}
              style={{
                borderRadius: 2,
                border: `1px solid ${c.inkHair}`,
                background: c.surfaceHi,
                padding: "10px 12px",
              }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div style={{ fontWeight: 600, color: c.ink }}>{neighbor.name}</div>
                  <div
                    style={{
                      marginTop: 4,
                      fontSize: 10,
                      letterSpacing: "0.14em",
                      textTransform: "uppercase",
                      color: c.inkFaint,
                    }}
                  >
                    {neighbor.type}
                  </div>
                </div>
                <div
                  style={{
                    flexShrink: 0,
                    borderRadius: "50%",
                    border: `1px solid ${c.inkHair}`,
                    background: c.paperWarm,
                    padding: "2px 8px",
                    fontSize: 10,
                    color: c.inkMuted,
                  }}
                >
                  {neighbor.documents.length} docs
                </div>
              </div>
              <div style={{ marginTop: 8, fontSize: 11, lineHeight: 1.6, color: c.inkMuted }}>
                {compactText(formatTags(neighbor.tags), 110)}
              </div>
              {neighbor.documents.length > 0 && (
                <div
                  style={{
                    marginTop: 8,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 6,
                    borderTop: `1px solid ${c.inkHair}`,
                    paddingTop: 8,
                  }}
                >
                  {neighbor.documents.slice(0, 2).map((doc) => (
                    <div
                      key={doc.id}
                      style={{
                        border: `1px solid ${c.inkHair}`,
                        background: c.paperWarm,
                        padding: "2px 8px",
                        fontSize: 10,
                        color: c.inkMuted,
                        borderRadius: "50%",
                      }}
                    >
                      {compactText(doc.title, 28)}
                    </div>
                  ))}
                  {neighbor.documents.length > 2 && (
                    <div
                      style={{
                        border: `1px solid ${c.inkHair}`,
                        background: c.paperWarm,
                        padding: "2px 8px",
                        fontSize: 10,
                        color: c.inkMuted,
                        borderRadius: "50%",
                      }}
                    >
                      +{neighbor.documents.length - 2}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div
              key={neighbor.id}
              style={{
                borderRadius: 2,
                border: `1px solid ${c.inkHair}`,
                background: c.surfaceHi,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontWeight: 600, color: c.ink }}>
                {neighbor.name} <span style={{ fontSize: 11, color: c.inkMuted }}>({neighbor.type})</span>
              </div>
              <div style={{ marginTop: 4, fontSize: 11, lineHeight: 1.55 }}>{formatTags(neighbor.tags)}</div>
              {neighbor.documents.length > 0 && (
                <div
                  style={{
                    marginTop: 8,
                    display: "grid",
                    gap: 4,
                    borderTop: `1px solid ${c.inkHair}`,
                    paddingTop: 8,
                  }}
                >
                  {neighbor.documents.map((doc) => (
                    <div key={doc.id} style={{ fontSize: 11, color: c.inkMuted }}>
                      {doc.title} <span style={{ fontSize: 10 }}>({doc.type} / {doc.status})</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        )}
        {graphContext.truncated && hiddenCount > 0 && (
          <div
            style={{
              borderRadius: 2,
              border: `1px solid ${c.inkHair}`,
              background: c.paperWarm,
              padding: "10px 12px",
              fontSize: 11,
            }}
          >
            還有 {hiddenCount} 個節點因長度限制未載入
          </div>
        )}
      </div>
    </details>
  );
}
