// ZenOS · TaskAttachments — Zen Ink migration (B4)
// Replaces Tailwind dark classes with zen primitives (Btn, Chip, Dialog).
// Image preview opens in zen/Dialog. Upload / delete / link CRUD preserved unchanged.
"use client";

// Inject spin keyframe once so loading spinners work without Tailwind animate-spin
if (typeof document !== "undefined") {
  const SPIN_STYLE_ID = "zen-spin-keyframe";
  if (!document.getElementById(SPIN_STYLE_ID)) {
    const style = document.createElement("style");
    style.id = SPIN_STYLE_ID;
    style.textContent = `@keyframes zen-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
    document.head.appendChild(style);
  }
}

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  ExternalLink,
  Upload,
  Loader2,
  AlertCircle,
  Paperclip,
  X,
} from "lucide-react";
import type { Task } from "@/types";
import {
  API_BASE,
  uploadTaskAttachment,
  uploadToSignedUrl,
  deleteTaskAttachment,
  addLinkAttachment,
} from "@/lib/api";
import { useInk } from "@/lib/zen-ink/tokens";
import { Btn } from "./zen/Btn";
import { Input } from "./zen/Input";
import { Dialog } from "./zen/Dialog";

type Attachment = NonNullable<Task["attachments"]>[number];

const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

interface UploadingFile {
  name: string;
  error?: string;
}

interface TaskAttachmentsProps {
  task: Task;
  token: string;
  onAttachmentsChanged: (attachments: Task["attachments"]) => void;
}

function isImageType(contentType?: string): boolean {
  return !!contentType && contentType.startsWith("image/");
}

/** Fetch an attachment via the proxy endpoint (with auth) and return a blob URL. */
function useAuthBlobUrl(proxyUrl: string | undefined, token: string) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!proxyUrl || !token) return;
    let revoked = false;
    fetch(`${API_BASE}${proxyUrl}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (blob && !revoked) setBlobUrl(URL.createObjectURL(blob));
      })
      .catch(() => {});
    return () => {
      revoked = true;
      setBlobUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    };
  }, [proxyUrl, token]);
  return blobUrl;
}

function AttachmentItem({
  att,
  onDelete,
  deleting,
  token,
}: {
  att: Attachment;
  onDelete: () => void;
  deleting: boolean;
  token: string;
}) {
  const t = useInk("light");
  const { c } = t;
  const type = att.type ?? (isImageType(att.content_type) ? "image" : "file");
  const blobUrl = useAuthBlobUrl(
    type === "image" || att.proxy_url ? att.proxy_url : undefined,
    token,
  );

  // Image preview dialog state
  const [previewOpen, setPreviewOpen] = useState(false);

  const handleDownload = useCallback(() => {
    if (!att.proxy_url || !token) return;
    fetch(`${API_BASE}${att.proxy_url}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = att.filename || "attachment";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => {});
  }, [att.proxy_url, att.filename, token]);

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 12,
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: t.radius,
          padding: 12,
          position: "relative",
          transition: "border-color 0.15s",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.borderColor = c.inkHairBold)}
        onMouseLeave={(e) => ((e.currentTarget as HTMLDivElement).style.borderColor = c.inkHair)}
      >
        {/* Thumbnail / icon */}
        {type === "image" && blobUrl ? (
          <button
            onClick={() => setPreviewOpen(true)}
            aria-label="預覽圖片"
            style={{
              flexShrink: 0,
              width: 64,
              height: 64,
              borderRadius: t.radius,
              overflow: "hidden",
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              padding: 0,
              cursor: "zoom-in",
            }}
          >
            <img
              src={blobUrl}
              alt={att.filename || "image"}
              style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              loading="lazy"
            />
          </button>
        ) : type === "image" && att.proxy_url ? (
          <div
            style={{
              flexShrink: 0,
              width: 64,
              height: 64,
              borderRadius: t.radius,
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Loader2 style={{ width: 18, height: 18, color: c.inkFaint, animation: "zen-spin 1s linear infinite" }} />
          </div>
        ) : type === "link" ? (
          <div
            style={{
              flexShrink: 0,
              padding: 8,
              borderRadius: t.radius,
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              display: "flex",
              alignItems: "center",
            }}
          >
            <ExternalLink style={{ width: 14, height: 14, color: c.inkMuted }} />
          </div>
        ) : (
          <div
            style={{
              flexShrink: 0,
              padding: 8,
              borderRadius: t.radius,
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              display: "flex",
              alignItems: "center",
            }}
          >
            <FileText style={{ width: 14, height: 14, color: c.inkMuted }} />
          </div>
        )}

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
          {type === "link" ? (
            <a
              href={att.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontFamily: t.fontBody,
                fontSize: 13,
                fontWeight: 500,
                color: c.inkMuted,
                textDecoration: "underline",
                textDecorationColor: c.inkHairBold,
                textUnderlineOffset: 2,
                display: "block",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                transition: "color 0.15s",
              }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = c.ink)}
              onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = c.inkMuted)}
            >
              {att.filename || att.url || "Link"}
            </a>
          ) : att.proxy_url ? (
            <button
              onClick={handleDownload}
              style={{
                fontFamily: t.fontBody,
                fontSize: 13,
                fontWeight: 500,
                color: c.ink,
                background: "transparent",
                border: "none",
                padding: 0,
                textAlign: "left",
                cursor: "pointer",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "block",
                width: "100%",
                transition: "color 0.15s",
              }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = c.inkMuted)}
              onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = c.ink)}
            >
              {att.filename || "File"}
            </button>
          ) : (
            <span style={{ fontFamily: t.fontBody, fontSize: 13, fontWeight: 500, color: c.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
              {att.filename || "File"}
            </span>
          )}
          {att.description && (
            <p style={{ fontFamily: t.fontBody, fontSize: 11, color: c.inkFaint, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {att.description}
            </p>
          )}
          {att.content_type && (
            <span style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              {att.content_type}
            </span>
          )}
        </div>

        {/* Delete */}
        <button
          onClick={onDelete}
          disabled={deleting}
          title="Remove attachment"
          style={{
            padding: 6,
            borderRadius: t.radius,
            border: `1px solid transparent`,
            background: "transparent",
            color: c.inkFaint,
            cursor: deleting ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            opacity: deleting ? 0.5 : 1,
            transition: "color 0.15s, background 0.15s, border-color 0.15s",
          }}
          onMouseEnter={(e) => {
            if (!deleting) {
              const btn = e.currentTarget as HTMLButtonElement;
              btn.style.color = c.vermillion;
              btn.style.background = c.vermSoft;
              btn.style.borderColor = c.vermLine;
            }
          }}
          onMouseLeave={(e) => {
            const btn = e.currentTarget as HTMLButtonElement;
            btn.style.color = c.inkFaint;
            btn.style.background = "transparent";
            btn.style.borderColor = "transparent";
          }}
        >
          {deleting ? (
            <Loader2 style={{ width: 13, height: 13, animation: "zen-spin 1s linear infinite" }} />
          ) : (
            <X style={{ width: 13, height: 13 }} />
          )}
        </button>
      </div>

      {/* Image preview dialog */}
      {type === "image" && blobUrl && (
        <Dialog
          t={t}
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          title={att.filename || "Image Preview"}
          size="lg"
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
            <img
              src={blobUrl}
              alt={att.filename || "image"}
              style={{ maxWidth: "100%", maxHeight: "70vh", objectFit: "contain", borderRadius: t.radius }}
            />
          </div>
        </Dialog>
      )}
    </>
  );
}

export function TaskAttachments({
  task,
  token,
  onAttachmentsChanged,
}: TaskAttachmentsProps) {
  const t = useInk("light");
  const { c } = t;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<UploadingFile[]>([]);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkUrl, setLinkUrl] = useState("");
  const [addingLink, setAddingLink] = useState(false);

  const attachments = task.attachments ?? [];

  const handleUpload = useCallback(
    async (files: FileList | File[]) => {
      setError(null);
      const fileArray = Array.from(files);

      for (const file of fileArray) {
        const isImage = file.type.startsWith("image/");
        const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_FILE_SIZE;
        if (file.size > maxSize) {
          const limitMb = maxSize / (1024 * 1024);
          setError(`"${file.name}" exceeds ${limitMb}MB limit for ${isImage ? "images" : "files"}`);
          continue;
        }

        const uploadEntry: UploadingFile = { name: file.name };
        setUploading((prev) => [...prev, uploadEntry]);

        try {
          const result = await uploadTaskAttachment(token, task.id, {
            filename: file.name,
            content_type: file.type || "application/octet-stream",
          });
          await uploadToSignedUrl(result.signed_put_url, file);
          const newAttachment: Attachment = {
            id: result.attachment_id,
            type: isImage ? "image" : "file",
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            proxy_url: result.proxy_url,
          };
          onAttachmentsChanged([...(task.attachments ?? []), newAttachment]);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Upload failed";
          setError(`Failed to upload "${file.name}": ${msg}`);
        } finally {
          setUploading((prev) => prev.filter((u) => u.name !== file.name));
        }
      }
    },
    [token, task.id, task.attachments, onAttachmentsChanged]
  );

  const handleDelete = useCallback(
    async (attachmentId: string) => {
      setError(null);
      setDeletingIds((prev) => new Set(prev).add(attachmentId));
      try {
        await deleteTaskAttachment(token, task.id, attachmentId);
        const updated = (task.attachments ?? []).filter((a) => a.id !== attachmentId);
        onAttachmentsChanged(updated);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Delete failed";
        setError(`Failed to delete attachment: ${msg}`);
      } finally {
        setDeletingIds((prev) => {
          const next = new Set(prev);
          next.delete(attachmentId);
          return next;
        });
      }
    },
    [token, task.id, task.attachments, onAttachmentsChanged]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        handleUpload(e.dataTransfer.files);
      }
    },
    [handleUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleAddLink = useCallback(async () => {
    const url = linkUrl.trim();
    if (!url) return;
    setError(null);
    setAddingLink(true);
    try {
      const result = await addLinkAttachment(token, task.id, { url });
      const newAttachment: Attachment = {
        id: result.attachment_id,
        type: "link",
        url,
        filename: url,
      };
      onAttachmentsChanged([...(task.attachments ?? []), newAttachment]);
      setLinkUrl("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to add link";
      setError(`Failed to add link: ${msg}`);
    } finally {
      setAddingLink(false);
    }
  }, [token, task.id, task.attachments, onAttachmentsChanged, linkUrl]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Section header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ width: 3, height: 16, borderRadius: 999, background: c.ocher, flexShrink: 0 }} />
        <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.16em", color: c.inkMuted }}>
          Attachments
        </span>
        {attachments.length > 0 && (
          <span style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint, fontWeight: 700 }}>
            ({attachments.length})
          </span>
        )}
      </div>

      {/* Existing attachments */}
      {attachments.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {attachments.map((att) => (
            <AttachmentItem
              key={att.id}
              att={att}
              onDelete={() => handleDelete(att.id)}
              deleting={deletingIds.has(att.id)}
              token={token}
            />
          ))}
        </div>
      )}

      {/* Uploading indicators */}
      {uploading.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {uploading.map((u) => (
            <div
              key={u.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: c.surface,
                border: `1px solid ${c.inkHair}`,
                borderRadius: t.radius,
                padding: 10,
              }}
            >
              <Loader2 style={{ width: 14, height: 14, color: c.inkMuted, animation: "zen-spin 1s linear infinite" }} />
              <span style={{ fontFamily: t.fontBody, fontSize: 13, color: c.inkMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                Uploading {u.name}...
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            background: c.vermSoft,
            border: `1px solid ${c.vermLine}`,
            borderRadius: t.radius,
            padding: 10,
          }}
        >
          <AlertCircle style={{ width: 14, height: 14, color: c.vermillion, flexShrink: 0, marginTop: 1 }} />
          <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.vermillion, margin: 0 }}>{error}</p>
        </div>
      )}

      {/* Link input */}
      <div style={{ display: "flex", gap: 8 }}>
        <Input
          t={t}
          size="sm"
          type="text"
          value={linkUrl}
          onChange={setLinkUrl}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); handleAddLink(); }
          }}
          placeholder="Paste a URL to attach..."
          disabled={addingLink}
          style={{ flex: 1 }}
        />
        <Btn
          t={t}
          variant="outline"
          size="sm"
          onClick={handleAddLink}
          style={{ opacity: addingLink || !linkUrl.trim() ? 0.5 : 1, cursor: addingLink || !linkUrl.trim() ? "not-allowed" : "pointer" }}
        >
          {addingLink ? (
            <Loader2 style={{ width: 12, height: 12, animation: "zen-spin 1s linear infinite" }} />
          ) : (
            <ExternalLink style={{ width: 12, height: 12 }} />
          )}
          Add
        </Btn>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          padding: 24,
          borderRadius: t.radius,
          border: `2px dashed ${isDragOver ? c.vermLine : c.inkHair}`,
          background: isDragOver ? c.vermSoft : c.paperWarm,
          cursor: "pointer",
          transition: "border-color 0.15s, background 0.15s",
        }}
        onMouseEnter={(e) => {
          if (!isDragOver) {
            (e.currentTarget as HTMLDivElement).style.borderColor = c.inkHairBold;
            (e.currentTarget as HTMLDivElement).style.background = c.surface;
          }
        }}
        onMouseLeave={(e) => {
          if (!isDragOver) {
            (e.currentTarget as HTMLDivElement).style.borderColor = c.inkHair;
            (e.currentTarget as HTMLDivElement).style.background = c.paperWarm;
          }
        }}
      >
        <div
          style={{
            padding: 8,
            borderRadius: "50%",
            background: isDragOver ? c.vermSoft : c.surface,
            border: `1px solid ${isDragOver ? c.vermLine : c.inkHair}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background 0.15s, border-color 0.15s",
          }}
        >
          {isDragOver ? (
            <Paperclip style={{ width: 18, height: 18, color: c.vermillion }} />
          ) : (
            <Upload style={{ width: 18, height: 18, color: c.inkFaint }} />
          )}
        </div>
        <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.inkMuted, margin: 0, textAlign: "center" }}>
          {isDragOver ? "Drop files here" : "Drag & drop files or click to upload"}
        </p>
        <p style={{ fontFamily: t.fontBody, fontSize: 10, color: c.inkFaint, margin: 0 }}>
          Images up to 10MB, other files up to 50MB
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleUpload(e.target.files);
            e.target.value = "";
          }
        }}
      />
    </div>
  );
}
