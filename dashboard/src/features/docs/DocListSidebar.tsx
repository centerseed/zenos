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

interface DocListSidebarProps {
  docs: Entity[];
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
function classifyDoc(doc: Entity): { group: DocGroup; productName?: string } {
  const details = (doc.details ?? {}) as Record<string, unknown>;
  if (details.pinned === true) return { group: "pinned" };

  // If parentId exists we treat it as a "project" doc
  if (doc.parentId) {
    return { group: "project", productName: String(details.product_name ?? doc.parentId) };
  }

  if (doc.visibility === "public") return { group: "team" };
  return { group: "personal" };
}

export function buildDocGroups(docs: Entity[]): DocGroupItem[] {
  const pinned: Entity[] = [];
  const personal: Entity[] = [];
  const team: Entity[] = [];
  const projectMap: Map<string, Entity[]> = new Map();

  for (const doc of docs) {
    const { group, productName } = classifyDoc(doc);
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
  selectedId,
  onSelect,
  onCreateNew,
  loading,
}: DocListSidebarProps) {
  const t = useInk();
  const { c, fontHead, fontMono, fontBody } = t;
  const [query, setQuery] = useState("");

  const filteredDocs = useMemo(() => {
    if (!query.trim()) return docs;
    const q = query.toLowerCase();
    return docs.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        (d.summary ?? "").toLowerCase().includes(q)
    );
  }, [docs, query]);

  const groups = useMemo(() => buildDocGroups(filteredDocs), [filteredDocs]);

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
      {groups.map((grp) => (
        <div key={grp.groupLabel} style={{ marginTop: 16 }}>
          <div
            data-testid={`doc-group-${grp.groupKey}`}
            style={{
              fontFamily: fontMono, fontSize: 9,
              color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase",
              padding: "0 4px 8px", display: "flex", alignItems: "center", gap: 8,
            }}
          >
            <span>{grp.groupLabel}</span>
            <div style={{ flex: 1, height: 1, background: c.inkHair }} />
            <span style={{ color: c.inkFaint }}>{grp.items.length}</span>
          </div>

          {grp.items.map((doc) => {
            const active = selectedId === doc.id;
            return (
              <button
                key={doc.id}
                onClick={() => onSelect(doc.id)}
                data-testid={`doc-item-${doc.id}`}
                style={{
                  display: "grid", gridTemplateColumns: "12px 1fr auto",
                  alignItems: "center", gap: 8, width: "100%",
                  padding: "6px 8px",
                  background: active ? c.surface : "transparent",
                  border: "none",
                  borderLeft: active ? `2px solid ${c.vermillion}` : "2px solid transparent",
                  cursor: "pointer", textAlign: "left",
                  color: active ? c.ink : c.inkSoft,
                  fontFamily: fontBody, fontSize: 12.5, marginBottom: 1,
                }}
              >
                <Icon d={ICONS.doc} size={11} style={{ color: c.inkFaint }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {doc.name}
                </span>
                <span style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint }}>
                  {formatDate(doc.updatedAt)}
                </span>
              </button>
            );
          })}
        </div>
      ))}
    </aside>
  );
}

function formatDate(date: Date | string | undefined | null): string {
  if (!date) return "";
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
