"use client";

import React, { useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "@/components/zen/Icons";
import type { Entity } from "@/types";

interface DocL3AccordionListProps {
  documents: Entity[];
  t: ReturnType<typeof useInk>;
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

export function DocL3AccordionList({ documents, t }: DocL3AccordionListProps) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [previewSourceId, setPreviewSourceId] = useState<string | null>(null);

  function toggleDoc(docId: string) {
    setExpandedDocId((prev) => (prev === docId ? null : docId));
    setPreviewSourceId(null);
  }

  if (documents.length === 0) {
    return (
      <div
        data-testid="doc-l3-accordion-list"
        style={{
          minHeight: 180,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          color: c.inkFaint,
          fontFamily: fontMono,
        }}
      >
        尚未掛上文件
      </div>
    );
  }

  return (
    <div
      data-testid="doc-l3-accordion-list"
      style={{ display: "flex", flexDirection: "column", gap: 1 }}
    >
      {documents.map((doc) => {
        const isExpanded = expandedDocId === doc.id;
        const sourceCount = doc.sources?.length ?? 0;
        const isIndex = doc.docRole === "index";
        const previewSource =
          previewSourceId !== null
            ? doc.sources?.find((s) => s.source_id === previewSourceId) ?? null
            : null;

        return (
          <div
            key={doc.id}
            style={{
              border: `1px solid ${c.inkHair}`,
              background: c.surface,
            }}
          >
            {/* Accordion row header */}
            <button
              data-testid={`doc-l3-row-${doc.id}`}
              onClick={() => toggleDoc(doc.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                width: "100%",
                padding: "12px 16px",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: fontBody,
              }}
            >
              {/* Chevron */}
              <Icon
                d={ICONS.chev}
                size={12}
                style={{
                  color: c.inkFaint,
                  transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "transform 120ms ease",
                  flexShrink: 0,
                }}
              />

              {/* Doc name */}
              <span
                style={{
                  flex: 1,
                  fontSize: 13,
                  fontWeight: 500,
                  color: c.ink,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {doc.name}
              </span>

              {/* doc_role badge */}
              <span
                style={{
                  padding: "1px 6px",
                  fontSize: 9,
                  fontFamily: fontMono,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: isIndex ? c.vermillion : c.inkFaint,
                  background: isIndex ? "rgba(190,60,50,0.08)" : "transparent",
                  border: isIndex ? `1px solid rgba(190,60,50,0.25)` : "none",
                  borderRadius: 2,
                  flexShrink: 0,
                }}
              >
                {isIndex ? "INDEX" : "SINGLE"}
              </span>

              {/* Source count badge */}
              <span
                data-testid={`doc-l3-source-count-${doc.id}`}
                style={{
                  fontFamily: fontMono,
                  fontSize: 10,
                  color: c.inkFaint,
                  flexShrink: 0,
                }}
              >
                {sourceCount === 0 ? "—" : `${sourceCount} sources`}
              </span>
            </button>

            {/* Expanded sources */}
            {isExpanded && (
              <div
                data-testid={`doc-l3-sources-${doc.id}`}
                style={{
                  borderTop: `1px solid ${c.inkHair}`,
                  padding: "8px 16px 12px 36px",
                }}
              >
                {sourceCount === 0 ? (
                  <div
                    style={{
                      fontSize: 12,
                      color: c.inkFaint,
                      fontFamily: fontBody,
                      padding: "8px 0",
                    }}
                  >
                    尚無來源
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {doc.sources.map((source, idx) => {
                      const isPreviewOpen = previewSourceId === source.source_id;
                      return (
                        <div key={source.source_id ?? `source-${idx}`}>
                          <button
                            data-testid={`doc-l3-source-item-${source.source_id}`}
                            onClick={() => {
                              setPreviewSourceId(
                                isPreviewOpen ? null : (source.source_id ?? null)
                              );
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                              width: "100%",
                              padding: "6px 8px",
                              background: isPreviewOpen ? c.surface : "transparent",
                              border: "none",
                              cursor: "pointer",
                              textAlign: "left",
                              fontFamily: fontBody,
                              fontSize: 12,
                              color: c.inkSoft,
                              borderRadius: 2,
                            }}
                          >
                            {/* Type badge */}
                            <span
                              style={{
                                padding: "1px 5px",
                                fontSize: 9,
                                fontFamily: fontMono,
                                letterSpacing: "0.06em",
                                textTransform: "uppercase",
                                color: "#fff",
                                background: c.inkSoft,
                                borderRadius: 2,
                                flexShrink: 0,
                              }}
                            >
                              {getSourceBadgeLabel(source.type)}
                            </span>
                            <span
                              style={{
                                flex: 1,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {source.label || source.uri}
                            </span>
                          </button>

                          {/* Inline preview panel */}
                          {isPreviewOpen && (
                            <div
                              data-testid="doc-l3-inline-preview"
                              style={{
                                margin: "4px 0 4px 8px",
                                padding: "12px 14px",
                                background: c.paperWarm,
                                border: `1px solid ${c.inkHair}`,
                                borderRadius: 2,
                                fontFamily: fontBody,
                              }}
                            >
                              <div
                                style={{
                                  fontSize: 13,
                                  fontWeight: 500,
                                  color: c.ink,
                                  marginBottom: 6,
                                }}
                              >
                                {source.label}
                              </div>
                              <div
                                style={{
                                  display: "flex",
                                  gap: 8,
                                  alignItems: "center",
                                  marginBottom: 8,
                                  flexWrap: "wrap",
                                }}
                              >
                                <span
                                  style={{
                                    padding: "1px 6px",
                                    fontSize: 9,
                                    fontFamily: fontMono,
                                    letterSpacing: "0.06em",
                                    textTransform: "uppercase",
                                    color: "#fff",
                                    background: c.inkSoft,
                                    borderRadius: 2,
                                  }}
                                >
                                  {getSourceBadgeLabel(source.type)}
                                </span>
                                {source.source_status && (
                                  <span
                                    style={{
                                      padding: "1px 6px",
                                      fontSize: 9,
                                      fontFamily: fontMono,
                                      letterSpacing: "0.06em",
                                      color: c.inkFaint,
                                      border: `1px solid ${c.inkHair}`,
                                      borderRadius: 2,
                                    }}
                                  >
                                    {source.source_status}
                                  </span>
                                )}
                                {source.doc_type && (
                                  <span
                                    style={{
                                      padding: "1px 6px",
                                      fontSize: 9,
                                      fontFamily: fontMono,
                                      letterSpacing: "0.06em",
                                      color: c.inkFaint,
                                      border: `1px solid ${c.inkHair}`,
                                      borderRadius: 2,
                                    }}
                                  >
                                    {source.doc_type}
                                  </span>
                                )}
                              </div>
                              {/* Snapshot summary with fallback chain */}
                              <div
                                style={{
                                  fontSize: 12,
                                  color: c.inkSoft,
                                  lineHeight: 1.6,
                                }}
                              >
                                {source.snapshot_summary ?? doc.summary ?? "—"}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
