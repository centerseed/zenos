"use client";

import React, { useState, useMemo } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Btn } from "@/components/zen/Btn";
import type { Entity } from "@/types";

export type DocGroup = "pinned" | "personal" | "team" | "project";

interface DocGroupItem {
  groupKey: DocGroup;
  groupLabel: string;
  items: Entity[];
}

interface PreparedDocGroup extends DocGroupItem {
  indexItems: Entity[];
  supportingItems: Entity[];
}

interface DocListSidebarProps {
  docs: Entity[];
  entities?: Entity[];
  scopeOptions?: Array<{ id: string; label: string; count: number }>;
  selectedScopeId?: string;
  totalDocCount?: number;
  onScopeChange?: (scopeId: string) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreateNew?: () => void;
  loading?: boolean;
}

/**
 * Classify a document entity into one of the four display groups.
 * Rules (Phase 1 — product_id-based heuristic):
 *  - pinned: entity has a custom "pinned" flag in details
 *  - personal: no parent and visibility != "public"  (approximation)
 *  - team: visibility == "public" and no product parent
 *  - project·{name}: entity has parentId pointing to a product entity
 */
function buildScopeLabel(entityId: string, entitiesById: Map<string, Entity>): string | null {
  const chain: Entity[] = [];
  const seen = new Set<string>();
  let current = entitiesById.get(entityId) ?? null;

  while (current && !seen.has(current.id)) {
    chain.unshift(current);
    seen.add(current.id);
    current = current.parentId ? entitiesById.get(current.parentId) ?? null : null;
  }

  if (chain.length === 0) return null;
  return chain.map((entity) => entity.name).join(" / ");
}

function classifyDoc(
  doc: Entity,
  entitiesById: Map<string, Entity> = new Map(),
): { group: DocGroup; productName?: string } {
  const details = (doc.details ?? {}) as Record<string, unknown>;
  if (details.pinned === true) return { group: "pinned" };

  // If parentId exists we treat it as a workspace-scoped doc. Resolve the full
  // root/module chain when the caller provides the entity index; falling back to
  // legacy product_name keeps older tests and payloads working.
  if (doc.parentId) {
    return {
      group: "project",
      productName:
        buildScopeLabel(doc.parentId, entitiesById) ??
        String(details.product_name ?? doc.parentId),
    };
  }

  if (doc.visibility === "public") return { group: "team" };
  return { group: "personal" };
}

export function buildDocGroups(
  docs: Entity[],
  entities: Entity[] = [],
): DocGroupItem[] {
  const pinned: Entity[] = [];
  const personal: Entity[] = [];
  const team: Entity[] = [];
  const projectMap: Map<string, Entity[]> = new Map();
  const entitiesById = new Map(entities.map((entity) => [entity.id, entity]));

  for (const doc of docs) {
    const { group, productName } = classifyDoc(doc, entitiesById);
    if (group === "pinned") {
      pinned.push(doc);
    } else if (group === "personal") {
      personal.push(doc);
    } else if (group === "team") {
      team.push(doc);
    } else if (group === "project") {
      const key = productName ?? "未命名專案";
      if (!projectMap.has(key)) projectMap.set(key, []);
      projectMap.get(key)!.push(doc);
    }
  }

  const groups: DocGroupItem[] = [];
  if (pinned.length > 0) groups.push({ groupKey: "pinned", groupLabel: "Pinned", items: pinned });
  if (personal.length > 0) groups.push({ groupKey: "personal", groupLabel: "個人", items: personal });
  if (team.length > 0) groups.push({ groupKey: "team", groupLabel: "團隊", items: team });
  for (const [name, items] of projectMap.entries()) {
    groups.push({ groupKey: "project", groupLabel: `專案 · ${name}`, items });
  }

  return groups;
}

export function DocListSidebar({
  docs,
  entities = [],
  scopeOptions = [],
  selectedScopeId = "all",
  totalDocCount,
  onScopeChange,
  selectedId,
  onSelect,
  onCreateNew,
  loading,
}: DocListSidebarProps) {
  const t = useInk();
  const { c, fontHead, fontMono, fontBody } = t;
  const [query, setQuery] = useState("");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [expandedDocIds, setExpandedDocIds] = useState<Set<string>>(new Set());
  const hasQuery = query.trim().length > 0;

  function toggleDocExpand(docId: string) {
    setExpandedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  }

  const filteredDocs = useMemo(() => {
    if (!query.trim()) return docs;
    const q = query.toLowerCase();
    return docs.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        (d.summary ?? "").toLowerCase().includes(q)
    );
  }, [docs, query]);

  const groups = useMemo(() => buildDocGroups(filteredDocs, entities), [filteredDocs, entities]);
  const preparedGroups = useMemo<PreparedDocGroup[]>(
    () =>
      groups.map((group) => {
        const indexItems = group.items.filter((doc) => doc.docRole === "index");
        return {
          ...group,
          indexItems,
          supportingItems: group.items.filter((doc) => doc.docRole !== "index"),
        };
      }),
    [groups],
  );

  function toggleGroup(groupLabel: string) {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupLabel)) {
        next.delete(groupLabel);
      } else {
        next.add(groupLabel);
      }
      return next;
    });
  }

  return (
    <aside
      data-testid="doc-list-sidebar"
      style={{
        borderRight: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
        padding: "24px 16px 16px",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase" }}>
            Docs
          </div>
          <div style={{ fontFamily: fontHead, fontSize: 18, fontWeight: 500, color: c.ink, letterSpacing: "0.04em", marginTop: 2 }}>
            文件
          </div>
        </div>
        <Btn
          t={t}
          variant="ink"
          size="sm"
          icon={ICONS.plus}
          onClick={onCreateNew}
          data-testid="new-doc-btn"
        >
          新
        </Btn>
      </div>

      {/* Search */}
      {onScopeChange ? (
        <div style={{ marginBottom: 14 }}>
          <label
            htmlFor="doc-scope-select"
            style={{
              display: "block",
              fontFamily: fontMono,
              fontSize: 9,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            Scope
          </label>
          <select
            id="doc-scope-select"
            value={selectedScopeId}
            onChange={(event) => onScopeChange(event.target.value)}
            style={{
              width: "100%",
              border: `1px solid ${c.inkHair}`,
              borderRadius: 2,
              background: c.surface,
              color: c.ink,
              fontFamily: fontBody,
              fontSize: 12,
              padding: "8px 10px",
              outline: "none",
            }}
          >
            <option value="all">全部文件 ({totalDocCount ?? docs.length})</option>
            {scopeOptions.map((scope) => (
              <option key={scope.id} value={scope.id}>
                {scope.label} ({scope.count})
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "7px 10px", marginBottom: 14,
        background: c.surface, border: `1px solid ${c.inkHair}`,
        borderRadius: 2,
      }}>
        <Icon d={ICONS.search} size={12} style={{ color: c.inkFaint }} />
        <input
          placeholder="搜尋文件…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            flex: 1, background: "transparent", border: "none", outline: "none",
            fontFamily: fontBody, fontSize: 12, color: c.ink,
          }}
        />
      </div>

      {loading && (
        <div style={{ fontSize: 12, color: c.inkFaint, padding: "8px 4px", fontFamily: fontBody }}>
          載入中…
        </div>
      )}

      {!loading && docs.length === 0 && (
        <div style={{ fontSize: 12, color: c.inkFaint, padding: "8px 4px", fontFamily: fontBody }}>
          還沒有文件。點「新」建立第一份。
        </div>
      )}

      {/* Groups */}
      {preparedGroups.map((grp) => {
        const expanded = hasQuery || expandedGroups.has(grp.groupLabel);
        const primaryItems = grp.indexItems.length > 0 ? grp.indexItems : grp.items.slice(0, 3);
        const visibleItems = expanded ? grp.items : primaryItems;
        const hiddenCount = Math.max(grp.items.length - visibleItems.length, 0);

        return (
        <div key={grp.groupLabel} style={{ marginTop: 16 }}>
          <button
            type="button"
            onClick={() => toggleGroup(grp.groupLabel)}
            data-testid={`doc-group-${grp.groupKey}`}
            style={{
              fontFamily: fontMono, fontSize: 9,
              color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase",
              padding: "0 4px 8px", display: "flex", alignItems: "center", gap: 8,
              width: "100%", border: "none", background: "transparent", cursor: "pointer",
              textAlign: "left",
            }}
          >
            <Icon
              d={ICONS.chev}
              size={10}
              style={{
                color: c.inkFaint,
                transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
                transition: "transform 120ms ease",
              }}
            />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {grp.groupLabel}
            </span>
            <div style={{ flex: 1, height: 1, background: c.inkHair }} />
            <span style={{ color: c.inkFaint }}>{grp.items.length}</span>
          </button>

          {visibleItems.map((doc) => {
            const active = selectedId === doc.id;
            const isIndex = doc.docRole === "index";
            const isDocExpanded = expandedDocIds.has(doc.id);
            const sourceCount = doc.sources?.length ?? 0;

            return (
              <div key={doc.id}>
                <div
                  data-testid={`doc-item-${doc.id}`}
                  style={{
                    display: "grid", gridTemplateColumns: "12px 1fr auto auto",
                    alignItems: "start", gap: 8, width: "100%",
                    padding: "8px 8px",
                    background: active ? c.surface : "transparent",
                    borderLeft: active ? `2px solid ${c.vermillion}` : "2px solid transparent",
                    marginBottom: 1,
                  }}
                >
                  {/* Chevron (only for index docs) */}
                  {isIndex ? (
                    <button
                      type="button"
                      data-testid={`doc-expand-chevron-${doc.id}`}
                      onClick={() => toggleDocExpand(doc.id)}
                      style={{
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        padding: 0,
                        display: "flex",
                        alignItems: "center",
                        marginTop: 1,
                      }}
                    >
                      <Icon
                        d={ICONS.chev}
                        size={10}
                        style={{
                          color: c.inkFaint,
                          transform: isDocExpanded ? "rotate(90deg)" : "rotate(0deg)",
                          transition: "transform 120ms ease",
                        }}
                      />
                    </button>
                  ) : (
                    <Icon d={ICONS.doc} size={11} style={{ color: c.inkFaint, marginTop: 1 }} />
                  )}

                  {/* Name button */}
                  <button
                    onClick={() => {
                      if (isIndex) {
                        toggleDocExpand(doc.id);
                      } else {
                        onSelect(doc.id);
                      }
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      padding: 0,
                      minWidth: 0,
                      color: active ? c.ink : c.inkSoft,
                      fontFamily: fontBody,
                      fontSize: 12.5,
                    }}
                  >
                    <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: isIndex ? 600 : 400 }}>
                      {doc.name}
                    </span>
                    {doc.summary ? (
                      <span
                        style={{
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          marginTop: 3,
                          color: c.inkFaint,
                          fontSize: 11,
                          lineHeight: 1.45,
                        }}
                      >
                        {doc.summary}
                      </span>
                    ) : null}
                  </button>

                  {/* Source count badge */}
                  <span
                    data-testid={`doc-source-count-${doc.id}`}
                    style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, marginTop: 2 }}
                  >
                    {sourceCount > 0 ? `${sourceCount}` : ""}
                  </span>

                  {/* doc_role / date badge */}
                  <span style={{ fontFamily: fontMono, fontSize: 9, color: isIndex ? c.vermillion : c.inkFaint, marginTop: 2 }}>
                    {isIndex ? "INDEX" : formatDate(doc.updatedAt)}
                  </span>
                </div>

                {/* Sources sub-list (index docs only, when expanded) */}
                {isIndex && isDocExpanded && (
                  <div style={{ paddingLeft: 28 }}>
                    {doc.sources && doc.sources.length > 0 ? (
                      doc.sources.map((source, idx) => (
                        <button
                          key={source.source_id ?? `source-${idx}`}
                          data-testid={`sidebar-source-item-${source.source_id}`}
                          onClick={() => onSelect(doc.id)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            width: "100%",
                            padding: "5px 8px",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            textAlign: "left",
                            fontFamily: fontBody,
                            fontSize: 11,
                            color: c.inkFaint,
                            marginBottom: 1,
                          }}
                        >
                          <span
                            style={{
                              display: "inline-block",
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: c.inkFaint,
                              flexShrink: 0,
                            }}
                          />
                          <span
                            style={{
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {source.label || source.uri}
                          </span>
                        </button>
                      ))
                    ) : (
                      <div style={{ fontSize: 11, color: c.inkFaint, padding: "5px 8px", fontFamily: fontBody }}>
                        尚無來源
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          {!expanded && hiddenCount > 0 ? (
            <button
              type="button"
              onClick={() => toggleGroup(grp.groupLabel)}
              style={{
                width: "100%",
                border: "none",
                background: "transparent",
                padding: "6px 8px 6px 28px",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
              }}
            >
              展開 {hiddenCount} 份支援文件
            </button>
          ) : null}
        </div>
        );
      })}
    </aside>
  );
}

function formatDate(date: Date | string | undefined | null): string {
  if (!date) return "";
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
