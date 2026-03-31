"use client";

import { useCallback, useRef, useState } from "react";
import {
  Image,
  FileText,
  ExternalLink,
  X,
  Upload,
  Loader2,
  AlertCircle,
  Paperclip,
} from "lucide-react";
import type { Task } from "@/types";
import {
  API_BASE,
  uploadTaskAttachment,
  uploadToSignedUrl,
  deleteTaskAttachment,
  addLinkAttachment,
} from "@/lib/api";

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

function AttachmentItem({
  att,
  onDelete,
  deleting,
}: {
  att: Attachment;
  onDelete: () => void;
  deleting: boolean;
}) {
  const type = att.type ?? (isImageType(att.content_type) ? "image" : "file");

  return (
    <div className="group relative flex items-start gap-3 bg-white/[0.04] border border-white/10 rounded-xl p-3 hover:bg-white/[0.06] transition-colors">
      {type === "image" && att.proxy_url ? (
        <div className="flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden bg-white/[0.06] border border-white/10">
          <img
            src={`${API_BASE}${att.proxy_url}`}
            alt={att.filename || "image"}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
      ) : type === "link" ? (
        <div className="flex-shrink-0 p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
          <ExternalLink className="w-4 h-4 text-blue-300" />
        </div>
      ) : (
        <div className="flex-shrink-0 p-2 rounded-lg bg-purple-500/20 border border-purple-500/30">
          <FileText className="w-4 h-4 text-purple-300" />
        </div>
      )}

      <div className="flex-1 min-w-0">
        {type === "link" ? (
          <a
            href={att.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors truncate block"
          >
            {att.filename || att.url || "Link"}
          </a>
        ) : att.proxy_url ? (
          <a
            href={`${API_BASE}${att.proxy_url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-white hover:text-blue-300 transition-colors truncate block"
          >
            {att.filename || "File"}
          </a>
        ) : (
          <span className="text-sm font-medium text-white truncate block">
            {att.filename || "File"}
          </span>
        )}
        {att.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {att.description}
          </p>
        )}
        {att.content_type && (
          <span className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">
            {att.content_type}
          </span>
        )}
      </div>

      <button
        onClick={onDelete}
        disabled={deleting}
        className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/20 text-muted-foreground hover:text-red-400 transition-all border border-transparent hover:border-red-500/30 disabled:opacity-50"
        title="Remove attachment"
      >
        {deleting ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <X className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
}

export function TaskAttachments({
  task,
  token,
  onAttachmentsChanged,
}: TaskAttachmentsProps) {
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
        // Validate file size
        const isImage = file.type.startsWith("image/");
        const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_FILE_SIZE;
        if (file.size > maxSize) {
          const limitMb = maxSize / (1024 * 1024);
          setError(
            `"${file.name}" exceeds ${limitMb}MB limit for ${isImage ? "images" : "files"}`
          );
          continue;
        }

        const uploadEntry: UploadingFile = { name: file.name };
        setUploading((prev) => [...prev, uploadEntry]);

        try {
          // Step 1: Get signed URL from backend
          const result = await uploadTaskAttachment(token, task.id, {
            filename: file.name,
            content_type: file.type || "application/octet-stream",
          });

          // Step 2: Upload directly to GCS
          await uploadToSignedUrl(result.signed_put_url, file);

          // Step 3: Update local state with the new attachment
          const newAttachment: Attachment = {
            id: result.attachment_id,
            type: isImage ? "image" : "file",
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            proxy_url: result.proxy_url,
          };
          onAttachmentsChanged([...(task.attachments ?? []), newAttachment]);
        } catch (err) {
          const msg =
            err instanceof Error ? err.message : "Upload failed";
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
        const updated = (task.attachments ?? []).filter(
          (a) => a.id !== attachmentId
        );
        onAttachmentsChanged(updated);
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Delete failed";
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
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-4 w-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
        <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">
          Attachments
        </h3>
        {attachments.length > 0 && (
          <span className="text-[10px] text-muted-foreground font-bold">
            ({attachments.length})
          </span>
        )}
      </div>

      {/* Existing attachments */}
      {attachments.length > 0 && (
        <div className="space-y-2">
          {attachments.map((att) => (
            <AttachmentItem
              key={att.id}
              att={att}
              onDelete={() => handleDelete(att.id)}
              deleting={deletingIds.has(att.id)}
            />
          ))}
        </div>
      )}

      {/* Uploading indicators */}
      {uploading.length > 0 && (
        <div className="space-y-2">
          {uploading.map((u) => (
            <div
              key={u.name}
              className="flex items-center gap-3 bg-white/[0.04] border border-white/10 rounded-xl p-3"
            >
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
              <span className="text-sm text-muted-foreground truncate">
                Uploading {u.name}...
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
          <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Link input */}
      <div className="flex gap-2">
        <input
          type="url"
          value={linkUrl}
          onChange={(e) => setLinkUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleAddLink();
            }
          }}
          placeholder="Paste a URL to attach..."
          className="flex-1 bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-muted-foreground focus:outline-none focus:border-blue-500/50 focus:bg-white/[0.06] transition-colors"
          disabled={addingLink}
        />
        <button
          onClick={handleAddLink}
          disabled={addingLink || !linkUrl.trim()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-500/20 border border-blue-500/30 text-blue-300 text-sm font-medium hover:bg-blue-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {addingLink ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <ExternalLink className="w-3.5 h-3.5" />
          )}
          Add
        </button>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all ${
          isDragOver
            ? "border-blue-500/50 bg-blue-500/10"
            : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
        }`}
      >
        <div
          className={`p-2 rounded-full transition-colors ${
            isDragOver ? "bg-blue-500/20" : "bg-white/[0.06]"
          }`}
        >
          {isDragOver ? (
            <Paperclip className="w-5 h-5 text-blue-400" />
          ) : (
            <Upload className="w-5 h-5 text-muted-foreground" />
          )}
        </div>
        <p className="text-xs text-muted-foreground text-center">
          {isDragOver
            ? "Drop files here"
            : "Drag & drop files or click to upload"}
        </p>
        <p className="text-[10px] text-muted-foreground/60">
          Images up to 10MB, other files up to 50MB
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
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
