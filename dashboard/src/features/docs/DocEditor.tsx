"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Btn } from "@/components/zen/Btn";
import { ICONS } from "@/components/zen/Icons";
import { RevisionConflictDialog, RevisionConflictInfo } from "./RevisionConflictDialog";
import type { DocumentDeliveryResponse } from "@/lib/api";

const AUTO_SAVE_DEBOUNCE_MS = 1500;

export interface DocEditorProps {
  docId: string;
  docMeta: DocumentDeliveryResponse["document"] | null;
  initialContent: string;
  baseRevisionId: string | null;
  token: string;
  onSaveSuccess?: (newRevisionId: string) => void;
  /** Triggered when user requests to reload (after conflict resolution) */
  onReloadRequest?: () => void;
}

type SaveStatus = "idle" | "saving" | "saved" | "conflict" | "error";

/**
 * Saves document content via POST /api/docs/{docId}/content.
 * Returns { revision_id } on success, throws with .status on HTTP error.
 */
async function saveContent(
  docId: string,
  token: string,
  content: string,
  baseRevisionId: string | null
): Promise<{ revision_id: string; canonical_path: string; current_revision_id?: string }> {
  const apiBase =
    process.env.NEXT_PUBLIC_MCP_API_URL ||
    "https://zenos-mcp-165893875709.asia-east1.run.app";

  const workspaceId =
    typeof window !== "undefined"
      ? window.localStorage.getItem("zenos.activeWorkspaceId")
      : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
  if (workspaceId) headers["X-Workspace-Id"] = workspaceId;

  const res = await fetch(`${apiBase}/api/docs/${docId}/content`, {
    method: "POST",
    headers,
    body: JSON.stringify({ base_revision_id: baseRevisionId, content }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as Record<string, unknown>;
    const err = new Error(String(body.message ?? body.error ?? "save failed")) as Error & { status: number; body: Record<string, unknown> };
    err.status = res.status;
    err.body = body;
    throw err;
  }

  return res.json();
}

export function DocEditor({
  docId,
  docMeta,
  initialContent,
  baseRevisionId: initialBaseRevisionId,
  token,
  onSaveSuccess,
  onReloadRequest,
}: DocEditorProps) {
  const t = useInk();
  const { c, fontHead, fontMono, fontBody } = t;

  const [content, setContent] = useState(initialContent);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [conflictInfo, setConflictInfo] = useState<RevisionConflictInfo | null>(null);
  const [conflictDialogOpen, setConflictDialogOpen] = useState(false);

  // Track latest base_revision_id across saves
  const baseRevisionIdRef = useRef(initialBaseRevisionId);
  // Track content for conflict dialog
  const contentRef = useRef(content);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  // Reset editor state ONLY when switching docs or parent reloads content
  // (e.g. after 409 conflict). Do NOT reset when only `initialBaseRevisionId`
  // changes — that happens after every save via `onSaveSuccess`, and the
  // internal `baseRevisionIdRef` is already kept fresh by `triggerSave`.
  // Including it as a dep would wipe the user's typed content after each save.
  useEffect(() => {
    setContent(initialContent);
    baseRevisionIdRef.current = initialBaseRevisionId;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId, initialContent]);

  const triggerSave = useCallback(async () => {
    if (!token) return;
    setSaveStatus("saving");
    try {
      const result = await saveContent(
        docId,
        token,
        contentRef.current,
        baseRevisionIdRef.current
      );
      baseRevisionIdRef.current = result.revision_id;
      setSaveStatus("saved");
      onSaveSuccess?.(result.revision_id);
      // Reset to idle after brief indication
      setTimeout(() => setSaveStatus((s) => (s === "saved" ? "idle" : s)), 2000);
    } catch (err) {
      const apiErr = err as Error & { status?: number; body?: Record<string, unknown> };
      if (apiErr.status === 409) {
        const body = apiErr.body ?? {};
        const currentRevId = String(body.current_revision_id ?? "unknown");
        setConflictInfo({
          current_revision_id: currentRevId,
          canonical_path: String(body.canonical_path ?? ""),
          localContent: contentRef.current,
        });
        setConflictDialogOpen(true);
        setSaveStatus("conflict");
      } else {
        setSaveStatus("error");
        console.error("[DocEditor] save error:", err);
      }
    }
  }, [docId, token, onSaveSuccess]);

  // Debounced auto-save on content change
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      triggerSave();
    }, AUTO_SAVE_DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  function handleConflictReload() {
    setConflictDialogOpen(false);
    setConflictInfo(null);
    setSaveStatus("idle");
    onReloadRequest?.();
  }

  function handleConflictCopyAndReload() {
    // clipboard write handled inside dialog; we just need to reload
    setConflictDialogOpen(false);
    setConflictInfo(null);
    setSaveStatus("idle");
    onReloadRequest?.();
  }

  // Derive breadcrumb from docMeta
  const scope = deriveScope(docMeta);
  const docType = docMeta?.sources?.[0]?.doc_type ?? "";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{
        padding: "20px 40px 16px",
        borderBottom: `1px solid ${c.inkHair}`,
        background: c.paper,
        flexShrink: 0,
      }}>
        {/* L2 breadcrumb */}
        <div
          data-testid="doc-breadcrumb"
          style={{
            fontFamily: fontMono,
            fontSize: 10,
            color: c.inkFaint,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            marginBottom: 6,
          }}
        >
          {scope && docType ? `${scope} · ${docType}` : scope || docType || "文件"}
        </div>

        {/* Title — editable inline */}
        <input
          type="text"
          value={docMeta?.name ?? ""}
          readOnly
          placeholder="未命名文件"
          style={{
            fontFamily: fontHead,
            fontSize: 28,
            fontWeight: 500,
            color: c.ink,
            background: "transparent",
            border: "none",
            outline: "none",
            padding: 0,
            width: "100%",
            letterSpacing: "0.02em",
          }}
        />

        {/* Meta row */}
        <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 12, color: c.inkMuted, fontFamily: fontBody }}>
          <span>
            更新 ·{" "}
            <span style={{ color: c.ink, fontFamily: fontMono }}>
              {docMeta?.last_published_at
                ? new Date(docMeta.last_published_at).toLocaleDateString("zh-TW")
                : "剛剛"}
            </span>
          </span>
          <span style={{ marginLeft: "auto", fontFamily: fontMono, fontSize: 10, color: saveStatusColor(saveStatus, c) }}>
            {saveStatusLabel(saveStatus)}
          </span>
        </div>

        {/* Toolbar */}
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <Btn t={t} variant="ghost" size="sm" icon={ICONS.spark}>Agent 改寫</Btn>
          <Btn t={t} variant="ghost" size="sm" icon={ICONS.link}>引用</Btn>
          <Btn t={t} variant="ghost" size="sm" icon={ICONS.users}>分享</Btn>
        </div>
      </div>

      {/* Editor area */}
      <div style={{ flex: 1, overflowY: "auto", padding: "32px 40px" }}>
        <textarea
          data-testid="doc-editor-textarea"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="開始輸入 Markdown…"
          style={{
            width: "100%",
            minHeight: "60vh",
            background: "transparent",
            border: "none",
            outline: "none",
            resize: "none",
            fontFamily: fontBody,
            fontSize: 14.5,
            color: c.ink,
            lineHeight: 1.85,
            padding: 0,
          }}
        />
      </div>

      {/* Revision conflict dialog */}
      <RevisionConflictDialog
        open={conflictDialogOpen}
        info={conflictInfo}
        onReload={handleConflictReload}
        onCopyAndReload={handleConflictCopyAndReload}
      />
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function deriveScope(docMeta: DocumentDeliveryResponse["document"] | null): string {
  if (!docMeta) return "";
  // Attempt to derive from doc name or canonical_path; fall back to empty
  // In practice, scope comes from the L2 entity the doc is linked to.
  // For Phase 1 UI we show a placeholder based on available data.
  const path = docMeta.canonical_path ?? "";
  if (path.startsWith("/docs/")) return "個人";
  return "個人";
}

function saveStatusLabel(status: SaveStatus): string {
  switch (status) {
    case "saving": return "儲存中…";
    case "saved": return "已儲存";
    case "conflict": return "版本衝突";
    case "error": return "儲存失敗";
    default: return "";
  }
}

function saveStatusColor(status: SaveStatus, c: ReturnType<typeof useInk>["c"]): string {
  switch (status) {
    case "saving": return c.ocher;
    case "saved": return c.jade;
    case "conflict": return c.vermillion;
    case "error": return c.vermillion;
    default: return c.inkFaint;
  }
}
