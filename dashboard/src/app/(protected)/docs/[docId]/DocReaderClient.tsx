"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useInk } from "@/lib/zen-ink/tokens";
import { useAuth } from "@/lib/auth";
import { Icon, ICONS } from "@/components/zen/Icons";
import { Btn } from "@/components/zen/Btn";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { DocOutline } from "@/features/docs/DocOutline";
import { DocSourceList } from "@/features/docs/DocSourceList";
import { ReSyncPromptDialog } from "@/features/docs/ReSyncPromptDialog";
import { getDocumentDelivery, getDocumentContent } from "@/lib/api";
import type { DocSource } from "@/features/docs/DocSourceList";

interface DocReaderState {
  name: string;
  summary: string;
  canonical_path?: string | null;
  primary_snapshot_revision_id?: string | null;
  last_published_at?: Date | null;
  delivery_status?: "ready" | "stale" | "blocked" | null;
  sources: DocSource[];
  content: string;
}

export default function DocReaderPage() {
  const t = useInk();
  const { c, fontHead, fontMono, fontBody } = t;
  const { user } = useAuth();
  const params = useParams();
  const router = useRouter();

  const docId = params?.docId as string;

  const [doc, setDoc] = useState<DocReaderState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [resyncSource, setResyncSource] = useState<DocSource | null>(null);
  const [resyncOpen, setResyncOpen] = useState(false);

  const loadDoc = useCallback(async () => {
    if (!user || !docId) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const [metaRes, contentRes] = await Promise.all([
        getDocumentDelivery(token, docId),
        getDocumentContent(token, docId),
      ]);

      if (!metaRes) {
        setError("找不到文件");
        return;
      }

      setDoc({
        name: metaRes.document.name ?? "文件",
        summary: metaRes.document.summary ?? "",
        canonical_path: metaRes.document.canonical_path,
        primary_snapshot_revision_id: metaRes.document.primary_snapshot_revision_id,
        last_published_at: metaRes.document.last_published_at,
        delivery_status: metaRes.document.delivery_status,
        sources: (metaRes.document.sources ?? []) as DocSource[],
        content: contentRes?.content ?? "",
      });
    } catch (err) {
      console.error("[DocReaderPage] load error:", err);
      setError("載入失敗，請稍後再試");
    } finally {
      setLoading(false);
    }
  }, [user, docId]);

  useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  function handleResyncRequest(source: DocSource) {
    setResyncSource(source);
    setResyncOpen(true);
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh", color: c.inkFaint, fontFamily: fontBody }}>
        載入中…
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh", gap: 12, color: c.inkFaint }}>
        <Icon d={ICONS.doc} size={32} style={{ color: c.inkHair }} />
        <div style={{ fontFamily: fontBody, fontSize: 13 }}>{error ?? "找不到文件"}</div>
        <Btn t={t} variant="ghost" size="sm" onClick={() => router.back()}>返回</Btn>
      </div>
    );
  }

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "1fr 280px",
      minHeight: "calc(100vh - 56px)",
      background: c.paper,
    }}>
      {/* Main content */}
      <div style={{ overflowY: "auto", padding: "40px 64px 80px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          {/* Breadcrumb */}
          <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
            文件
          </div>

          {/* Title */}
          <h1 style={{ fontFamily: fontHead, fontSize: 36, fontWeight: 500, color: c.ink, margin: 0, letterSpacing: "0.02em", lineHeight: 1.2 }}>
            {doc.name}
          </h1>

          {/* Meta */}
          <div style={{ display: "flex", gap: 16, marginTop: 14, fontSize: 12, color: c.inkMuted }}>
            {doc.last_published_at && (
              <span>
                發布 ·{" "}
                <span style={{ color: c.ink, fontFamily: fontMono }}>
                  {new Date(doc.last_published_at).toLocaleDateString("zh-TW")}
                </span>
              </span>
            )}
            {doc.delivery_status && (
              <span>
                狀態 ·{" "}
                <span style={{ color: doc.delivery_status === "ready" ? c.jade : c.ocher, fontFamily: fontMono }}>
                  {doc.delivery_status === "ready" ? "已發布" : doc.delivery_status}
                </span>
              </span>
            )}
          </div>

          {/* Divider */}
          <div style={{ borderBottom: `1px solid ${c.inkHair}`, marginTop: 20, marginBottom: 32 }} />

          {/* Rendered markdown */}
          {doc.content ? (
            <MarkdownRenderer content={doc.content} />
          ) : (
            <div style={{ fontSize: 13, color: c.inkFaint, fontFamily: fontBody }}>
              這份文件還沒有內容。
            </div>
          )}
        </div>
      </div>

      {/* Right rail */}
      <aside style={{
        borderLeft: `1px solid ${c.inkHair}`,
        background: c.paperWarm,
        padding: "24px 16px",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}>
        {/* Outline */}
        {doc.content && (
          <div>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
              大綱
            </div>
            <DocOutline content={doc.content} />
          </div>
        )}

        {/* Sources */}
        {doc.sources.length > 0 && (
          <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 16 }}>
            <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 10 }}>
              引用 · 來源
            </div>
            <DocSourceList
              sources={doc.sources}
              onResyncRequest={handleResyncRequest}
            />
          </div>
        )}

        {/* Actions */}
        <div style={{ borderTop: `1px solid ${c.inkHair}`, paddingTop: 16 }}>
          <Btn
            t={t}
            variant="ghost"
            size="sm"
            icon={ICONS.doc}
            onClick={() => router.push(`/docs?edit=${docId}`)}
          >
            編輯此文件
          </Btn>
        </div>
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
