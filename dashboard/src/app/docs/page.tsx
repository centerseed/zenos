"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import {
  createDocumentShareLink,
  getDocumentContent,
  getDocumentDelivery,
  publishDocumentSnapshot,
  updateDocumentVisibility,
} from "@/lib/api";
import type { EntityVisibility } from "@/types";

function DocumentReaderInner() {
  const searchParams = useSearchParams();
  const docId = searchParams.get("docId")?.trim() ?? "";
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [savingVisibility, setSavingVisibility] = useState(false);
  const [metadata, setMetadata] = useState<Awaited<ReturnType<typeof getDocumentDelivery>>>(null);
  const [content, setContent] = useState<string>("");
  const [message, setMessage] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [selectedVisibility, setSelectedVisibility] = useState<EntityVisibility>("public");

  const currentVisibility = useMemo(() => {
    const visibility = metadata?.document?.visibility;
    if (visibility === "restricted" || visibility === "confidential") return visibility;
    return "public";
  }, [metadata]);

  useEffect(() => {
    setSelectedVisibility(currentVisibility);
  }, [currentVisibility]);

  useEffect(() => {
    if (!docId) {
      setLoading(false);
      setMessage("缺少 docId，請從文件節點的 Reader 連結進入。");
      return;
    }
    if (!user || !docId) return;
    const authUser = user;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setMessage(null);
      try {
        const token = await authUser.getIdToken();
        const [meta, body] = await Promise.all([
          getDocumentDelivery(token, docId),
          getDocumentContent(token, docId),
        ]);
        if (cancelled) return;
        setMetadata(meta);
        setContent(body?.content ?? "");
        if (!body?.content) {
          setMessage("這份文件尚未發布 snapshot。請先點擊 Publish Snapshot。");
        }
      } catch {
        if (cancelled) return;
        setMessage("載入文件失敗。");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [user, docId]);

  async function handlePublish() {
    if (!user || !docId) return;
    setPublishing(true);
    setMessage(null);
    try {
      const token = await user.getIdToken();
      const result = await publishDocumentSnapshot(token, docId);
      if (!result) {
        setMessage("發布失敗。請確認 source 可讀（Phase 1 目前只支援 GitHub source）。");
        return;
      }
      const [meta, body] = await Promise.all([
        getDocumentDelivery(token, docId),
        getDocumentContent(token, docId),
      ]);
      setMetadata(meta);
      setContent(body?.content ?? "");
      setMessage("Snapshot 發布完成。");
    } finally {
      setPublishing(false);
    }
  }

  async function handleSaveVisibility() {
    if (!user || !docId) return;
    setSavingVisibility(true);
    setMessage(null);
    try {
      const token = await user.getIdToken();
      const result = await updateDocumentVisibility(token, docId, selectedVisibility);
      if (!result) {
        setMessage("更新 visibility 失敗。");
        return;
      }
      const meta = await getDocumentDelivery(token, docId);
      setMetadata(meta);
      setMessage("Visibility 已更新。");
    } finally {
      setSavingVisibility(false);
    }
  }

  async function handleCreateShareLink() {
    if (!user || !docId) return;
    setMessage(null);
    const token = await user.getIdToken();
    const result = await createDocumentShareLink(token, docId, { expires_in_hours: 24 * 7 });
    if (!result) {
      setMessage("建立分享連結失敗。");
      return;
    }
    const url = `${window.location.origin}${result.share_url}`;
    setShareUrl(url);
    try {
      await navigator.clipboard.writeText(url);
      setMessage("已建立分享連結並複製到剪貼簿。");
    } catch {
      setMessage("已建立分享連結。");
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <AppNav />
      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
          <div>
            <h1 className="text-lg font-semibold">{metadata?.document?.name ?? docId}</h1>
            <p className="text-xs text-muted-foreground">
              {metadata?.document?.canonical_path ?? `/docs/${docId}`} · {metadata?.document?.delivery_status ?? "unpublished"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="rounded-md border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs text-primary disabled:opacity-50"
            >
              {publishing ? "Publishing..." : "Publish Snapshot"}
            </button>
            <button
              onClick={handleCreateShareLink}
              className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-secondary/60"
            >
              Create Share Link
            </button>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap items-end gap-2 rounded-xl border border-border bg-card p-4">
          <label className="text-xs text-muted-foreground">Visibility</label>
          <select
            value={selectedVisibility}
            onChange={(e) => setSelectedVisibility(e.target.value as EntityVisibility)}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          >
            <option value="public">public</option>
            <option value="restricted">restricted</option>
            <option value="confidential">confidential</option>
          </select>
          <button
            onClick={handleSaveVisibility}
            disabled={savingVisibility}
            className="rounded-md border border-border px-3 py-1 text-xs hover:bg-secondary/60 disabled:opacity-50"
          >
            {savingVisibility ? "Saving..." : "Save"}
          </button>
          {shareUrl && (
            <a
              href={shareUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-xs text-cyan-400 underline underline-offset-2"
            >
              Open Share Link
            </a>
          )}
        </div>

        {message && (
          <div className="mb-4 rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
            {message}
          </div>
        )}

        {loading ? (
          <LoadingState label="Loading document..." />
        ) : content ? (
          <article className="rounded-xl border border-border bg-card p-5">
            <MarkdownRenderer content={content} />
          </article>
        ) : (
          <div className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
            尚無可讀內容。
          </div>
        )}
      </main>
    </div>
  );
}

export default function DocumentReaderPage() {
  return (
    <AuthGuard>
      <Suspense fallback={<LoadingState label="Loading document..." />}>
        <DocumentReaderInner />
      </Suspense>
    </AuthGuard>
  );
}
