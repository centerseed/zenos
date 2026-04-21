"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getSharedDocumentByToken } from "@/lib/api";
import { LoadingState } from "@/components/LoadingState";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";

function SharedDocumentPageInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState<string>("Shared Document");
  const [content, setContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("缺少 token，請使用完整分享連結。");
      setLoading(false);
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      const payload = await getSharedDocumentByToken(token);
      if (cancelled) return;
      if (!payload) {
        setError("分享連結不可用（已失效、已撤銷或不存在）。");
      } else {
        setTitle(payload.doc?.name ?? "Shared Document");
        setContent(payload.content ?? "");
      }
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="mx-auto min-h-screen w-full max-w-4xl bg-base px-4 py-8 text-foreground sm:px-6">
      <header className="mb-6 border-b bd-hair pb-3">
        <h1 className="text-xl font-semibold">{title}</h1>
      </header>
      {loading ? (
        <LoadingState label="Loading shared document..." />
      ) : error ? (
        <div className="rounded-zen border bd-hair bg-panel p-5 text-sm text-dim">{error}</div>
      ) : (
        <article className="rounded-zen border bd-hair bg-panel p-5">
          <MarkdownRenderer content={content} />
        </article>
      )}
    </main>
  );
}

export default function SharedDocumentPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading shared document..." />}>
      <SharedDocumentPageInner />
    </Suspense>
  );
}
