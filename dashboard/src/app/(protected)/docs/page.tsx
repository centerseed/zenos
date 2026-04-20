"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useInk } from "@/lib/zen-ink/tokens";
import { useAuth } from "@/lib/auth";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Btn } from "@/components/zen/Btn";

import { DocListSidebar } from "@/features/docs/DocListSidebar";
import { DocEditor } from "@/features/docs/DocEditor";
import { DocOutline } from "@/features/docs/DocOutline";
import { DocSourceList } from "@/features/docs/DocSourceList";
import { ReSyncPromptDialog } from "@/features/docs/ReSyncPromptDialog";

import {
  listDocs,
  createDoc,
  getDocumentDelivery,
  getDocumentContent,
} from "@/lib/api";
import type { Entity } from "@/types";
import type { DocSource } from "@/features/docs/DocSourceList";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DocMeta {
  id: string;
  name: string;
  summary: string;
  visibility: Entity["visibility"];
  sources: DocSource[];
  doc_role?: "single" | "index" | null;
  canonical_path?: string | null;
  primary_snapshot_revision_id?: string | null;
  last_published_at?: Date | null;
  delivery_status?: "ready" | "stale" | "blocked" | null;
}

interface DocContent {
  content: string;
  revision_id: string | null;  // null = no revision yet (new doc or pre-existing without Delivery Snapshot)
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DocsPage() {
  const t = useInk();
  const { c } = t;
  const { user } = useAuth();
  const router = useRouter();

  // Doc list
  const [docs, setDocs] = useState<Entity[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);

  // Selected doc
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docMeta, setDocMeta] = useState<DocMeta | null>(null);
  const [docContent, setDocContent] = useState<DocContent | null>(null);
  const [docLoading, setDocLoading] = useState(false);

  // Re-sync dialog
  const [resyncSource, setResyncSource] = useState<DocSource | null>(null);
  const [resyncOpen, setResyncOpen] = useState(false);

  // ─── Load doc list ─────────────────────────────────────────────────────────

  const loadDocs = useCallback(async () => {
    if (!user) return;
    setDocsLoading(true);
    try {
      const token = await user.getIdToken();
      const list = await listDocs(token);
      setDocs(list);
    } catch (err) {
      console.error("[DocsPage] loadDocs error:", err);
    } finally {
      setDocsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  // ─── Load selected doc ─────────────────────────────────────────────────────

  const loadDoc = useCallback(async (docId: string) => {
    if (!user) return;
    setDocLoading(true);
    try {
      const token = await user.getIdToken();
      const [metaRes, contentRes] = await Promise.all([
        getDocumentDelivery(token, docId),
        getDocumentContent(token, docId),
      ]);

      if (metaRes?.document) {
        setDocMeta({
          ...metaRes.document,
          sources: (metaRes.document.sources ?? []) as DocSource[],
        });
      }

      if (contentRes) {
        const revId =
          (contentRes.revision as Record<string, unknown> | null | undefined)?.[
            "revision_id"
          ] as string | undefined ??
          String((contentRes.revision as Record<string, unknown> | null | undefined)?.["id"] ?? "");
        setDocContent({
          content: contentRes.content ?? "",
          revision_id: revId || null,
        });
      } else {
        // No snapshot yet (new doc or pre-existing without Delivery). Start with empty editable state.
        // First save sends base_revision_id=null → backend creates rev-1 (see dashboard_api.py:2488).
        setDocContent({ content: "", revision_id: null });
      }
    } catch (err) {
      console.error("[DocsPage] loadDoc error:", err);
    } finally {
      setDocLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (selectedDocId) {
      loadDoc(selectedDocId);
    }
  }, [selectedDocId, loadDoc]);

  // ─── Create new doc ────────────────────────────────────────────────────────

  const handleCreateNew = useCallback(async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const result = await createDoc(token, { name: "未命名文件" });
      // Refresh list
      await loadDocs();
      // Navigate to editor for the new doc
      setSelectedDocId(result.doc_id ?? result.entity?.id);
    } catch (err) {
      console.error("[DocsPage] createDoc error:", err);
    }
  }, [user, loadDocs]);

  // ─── Resync handler ────────────────────────────────────────────────────────

  function handleResyncRequest(source: DocSource) {
    setResyncSource(source);
    setResyncOpen(true);
  }

  // ─── Save success ─────────────────────────────────────────────────────────

  function handleSaveSuccess(newRevisionId: string) {
    setDocContent((prev) => prev ? { ...prev, revision_id: newRevisionId } : prev);
  }

  // ─── Reload doc (after conflict) ──────────────────────────────────────────

  function handleReloadRequest() {
    if (selectedDocId) loadDoc(selectedDocId);
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "280px 1fr 300px",
      minHeight: "calc(100vh - 56px)",
      background: c.paper,
    }}>
      {/* Left sidebar — doc list */}
      <DocListSidebar
        docs={docs}
        selectedId={selectedDocId}
        onSelect={setSelectedDocId}
        onCreateNew={handleCreateNew}
        loading={docsLoading}
      />

      {/* Center — editor */}
      <div style={{ overflowY: "auto", background: c.paper }}>
        {docLoading && (
          <div style={{ padding: 40, fontSize: 13, color: c.inkFaint, fontFamily: t.fontBody }}>
            載入中…
          </div>
        )}
        {!selectedDocId && !docLoading && (
          <EmptyState t={t} onCreateNew={handleCreateNew} />
        )}
        {selectedDocId && !docLoading && docContent && user && (
          <DocEditorWrapper
            docId={selectedDocId}
            docMeta={docMeta}
            docContent={docContent}
            user={user}
            onSaveSuccess={handleSaveSuccess}
            onReloadRequest={handleReloadRequest}
          />
        )}
      </div>

      {/* Right rail — outline + sources */}
      <aside style={{
        borderLeft: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
        padding: "24px 16px",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}>
        {docMeta && (
          <>
            <DocOutlineSection
              t={t}
              content={docContent?.content ?? ""}
            />

            <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 16 }}>
              <div style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
                引用 · 來源
              </div>
              <DocSourceList
                sources={docMeta.sources ?? []}
                onResyncRequest={handleResyncRequest}
              />
            </div>
          </>
        )}
      </aside>

      {/* Re-sync dialog */}
      <ReSyncPromptDialog
        open={resyncOpen}
        onOpenChange={setResyncOpen}
        source={resyncSource}
      />
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface DocEditorWrapperProps {
  docId: string;
  docMeta: DocMeta | null;
  docContent: DocContent;
  user: { getIdToken: () => Promise<string> };
  onSaveSuccess: (revId: string) => void;
  onReloadRequest: () => void;
}

function DocEditorWrapper({
  docId,
  docMeta,
  docContent,
  user,
  onSaveSuccess,
  onReloadRequest,
}: DocEditorWrapperProps) {
  const [token, setToken] = useState<string>("");

  useEffect(() => {
    user.getIdToken().then(setToken).catch(console.error);
  }, [user]);

  if (!token) return null;

  return (
    <DocEditor
      docId={docId}
      docMeta={docMeta as Parameters<typeof DocEditor>[0]["docMeta"]}
      initialContent={docContent.content}
      baseRevisionId={docContent.revision_id}
      token={token}
      onSaveSuccess={onSaveSuccess}
      onReloadRequest={onReloadRequest}
    />
  );
}

function DocOutlineSection({
  t,
  content,
}: {
  t: ReturnType<typeof useInk>;
  content: string;
}) {
  const { c } = t;
  return (
    <div>
      <div style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
        大綱
      </div>
      <DocOutline content={content} />
    </div>
  );
}

function EmptyState({
  t,
  onCreateNew,
}: {
  t: ReturnType<typeof useInk>;
  onCreateNew?: () => void;
}) {
  const { c, fontHead, fontBody } = t;
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "60vh",
      gap: 16,
      color: c.inkFaint,
    }}>
      <Icon d={ICONS.doc} size={40} style={{ color: c.inkHair }} />
      <div style={{ fontFamily: fontHead, fontSize: 18, color: c.inkMuted }}>
        選擇一份文件或建立新文件
      </div>
      <Btn t={t} variant="outline" size="md" icon={ICONS.plus} onClick={onCreateNew}>
        新文件
      </Btn>
    </div>
  );
}
