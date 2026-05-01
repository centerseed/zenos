"use client";

import React from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon } from "@/components/zen/Icons";

const ICON_REFRESH = "M4 4v5h.582m15.356 2A8 8 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8 8 0 01-15.357-2m15.357 2H15";
import { useRouter } from "next/navigation";

/** Extended source type with helper-ingest fields */
export interface DocSource {
  source_id?: string;
  uri: string;
  label: string;
  type: string;
  source_status?: string;
  doc_type?: string;
  external_id?: string;
  external_updated_at?: string | null;
  last_synced_at?: string | null;
  snapshot_summary?: string | null;
}

interface DocSourceListProps {
  sources: DocSource[];
  onResyncRequest?: (source: DocSource) => void;
}

const STALE_DAYS = 14;

function isStale(source: DocSource): boolean {
  if (!source.last_synced_at) return false;
  const lastSynced = new Date(source.last_synced_at);
  const now = new Date();
  const diffDays = (now.getTime() - lastSynced.getTime()) / (1000 * 60 * 60 * 24);
  return diffDays > STALE_DAYS;
}

function hasInvertedTimestamps(source: DocSource): boolean {
  if (!source.external_updated_at || !source.last_synced_at) return false;
  return new Date(source.external_updated_at) > new Date(source.last_synced_at);
}

function getSourceBadgeLabel(type: string): string {
  switch (type) {
    case "zenos_native": return "ZenOS";
    case "github": return "GitHub";
    case "notion": return "Notion";
    case "gdrive": return "GDrive";
    case "local": return "Local";
    default: return type;
  }
}

function getSourceBadgeColor(type: string, c: ReturnType<typeof useInk>["c"]): string {
  switch (type) {
    case "zenos_native": return c.vermillion;
    case "github": return c.inkSoft;
    case "notion": return "#2383E2";
    case "gdrive": return "#4285F4";
    case "local": return c.jade;
    default: return c.inkFaint;
  }
}

export function DocSourceList({ sources, onResyncRequest }: DocSourceListProps) {
  const t = useInk();
  const { c, fontMono, fontBody } = t;
  const router = useRouter();

  if (!sources || sources.length === 0) {
    return (
      <div style={{ fontSize: 12, color: c.inkFaint, padding: "8px 0" }}>
        無來源
      </div>
    );
  }

  function handleSourceClick(source: DocSource) {
    if (source.type === "zenos_native") {
      // Extract doc_id from uri — format is /docs/{doc_id}
      const match = source.uri.match(/^\/docs\/(.+)$/);
      if (match) {
        router.push(`/docs/${match[1]}`);
      } else {
        router.push(source.uri);
      }
    } else {
      window.open(source.uri, "_blank", "noopener,noreferrer");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {sources.map((source, i) => {
        const stale = isStale(source);
        const invertedTs = hasInvertedTimestamps(source);
        const badgeColor = getSourceBadgeColor(source.type, c);
        const badgeLabel = getSourceBadgeLabel(source.type);

        return (
          <div
            key={source.source_id ?? `source-${i}`}
            style={{
              padding: "8px 0",
              borderBottom: i < sources.length - 1 ? `1px solid ${c.inkHair}` : "none",
            }}
          >
            {/* Main row */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {/* Source type badge */}
              <span
                data-testid="source-badge"
                data-source-type={source.type}
                style={{
                  display: "inline-block",
                  padding: "1px 6px",
                  fontSize: 9,
                  fontFamily: fontMono,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "#fff",
                  background: badgeColor,
                  borderRadius: 2,
                  flexShrink: 0,
                }}
              >
                {badgeLabel}
              </span>

              {/* Label / URI */}
              <button
                onClick={() => handleSourceClick(source)}
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  fontSize: 12,
                  color: c.ink,
                  fontFamily: fontBody,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  padding: 0,
                }}
              >
                {source.label || source.uri}
              </button>

              {/* Stale badge */}
              {stale && (
                <span
                  data-testid="stale-badge"
                  style={{
                    display: "inline-block",
                    padding: "1px 6px",
                    fontSize: 9,
                    fontFamily: fontMono,
                    letterSpacing: "0.06em",
                    color: c.ocher,
                    background: "rgba(180,132,50,0.12)",
                    border: `1px solid rgba(180,132,50,0.30)`,
                    borderRadius: 2,
                    flexShrink: 0,
                  }}
                >
                  stale
                </span>
              )}

              {/* Resync button — only for external sources */}
              {source.type !== "zenos_native" && source.type !== "local" && onResyncRequest && (
                <button
                  data-testid="resync-button"
                  onClick={() => onResyncRequest(source)}
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    padding: "2px 4px",
                    color: c.inkFaint,
                    fontSize: 10,
                    fontFamily: fontMono,
                    letterSpacing: "0.04em",
                    flexShrink: 0,
                  }}
                  title="重新同步"
                >
                  <Icon d={ICON_REFRESH} size={11} style={{ color: c.inkFaint }} />
                </button>
              )}
            </div>

            {/* Inverted timestamps warning */}
            {invertedTs && (
              <div
                data-testid="inverted-ts-warning"
                style={{
                  marginTop: 4,
                  padding: "4px 8px",
                  fontSize: 11,
                  color: c.vermillion,
                  background: c.vermSoft,
                  border: `1px solid ${c.vermLine}`,
                  borderRadius: 2,
                  fontFamily: fontBody,
                }}
              >
                推入內容可能較舊，建議重新同步
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
