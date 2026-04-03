"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import type { Entity, Task, TaskComment } from "@/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { TaskAttachments } from "./TaskAttachments";
import { useAuth } from "@/lib/auth";
import { getTaskComments, createTaskComment, deleteTaskComment } from "@/lib/api";
import {
  AlertTriangle,
  ArrowUp,
  Minus,
  ArrowDown,
  X,
  Layers,
  User,
  ExternalLink,
  Bot,
  Hash,
  Link2,
  Clock,
  Check,
  ChevronDown,
  Trash2,
  MessageSquare,
} from "lucide-react";

interface TaskDetailDrawerProps {
  task: Task | null;
  onClose: () => void;
  entityNames?: Record<string, string>;
  entitiesById?: Record<string, Entity>;
  onTaskUpdated?: () => void;
  onUpdateTask?: (taskId: string, updates: Record<string, unknown>) => Promise<void>;
  onConfirmTask?: (taskId: string, data: { action: "approve" | "reject"; rejection_reason?: string }) => Promise<void>;
}

const priorityIcons: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="w-4 h-4 text-red-400" />,
  high: <ArrowUp className="w-4 h-4 text-orange-400" />,
  medium: <Minus className="w-4 h-4 text-yellow-400" />,
  low: <ArrowDown className="w-4 h-4 text-blue-400" />,
};

const priorityBg: Record<string, string> = {
  critical: "bg-red-500/20 border-red-500/30 text-red-300",
  high: "bg-orange-500/20 border-orange-500/30 text-orange-300",
  medium: "bg-yellow-500/20 border-yellow-500/30 text-yellow-300",
  low: "bg-blue-500/20 border-blue-500/30 text-blue-300",
};

const statusColors: Record<string, string> = {
  todo: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  in_progress: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  review: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  done: "bg-green-500/10 text-green-400 border-green-500/20",
  blocked: "bg-red-500/10 text-red-400 border-red-500/20",
  backlog: "bg-gray-500/10 text-gray-400 border-gray-500/20",
  cancelled: "bg-gray-500/10 text-gray-500 border-gray-500/20",
};

/** Valid status transitions: from -> to[] */
const STATUS_TRANSITIONS: Record<string, string[]> = {
  todo: ["in_progress"],
  in_progress: ["todo", "review"],
  review: ["in_progress", "done"],
  done: ["todo"],
  cancelled: [],
  blocked: ["todo", "in_progress"],
};

function formatDate(date: Date | null): string {
  if (!date) return "No date set";
  return date.toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function ContextCard({ entity }: { entity?: Entity; name: string }) {
  if (!entity) return null;

  return (
    <Link href={`/knowledge-map?id=${entity.id}`} className="block group">
      <div className="bg-white/[0.04] border border-white/10 rounded-xl p-4 space-y-3 group-hover:bg-white/[0.08] group-hover:border-blue-500/30 transition-all shadow-sm overflow-hidden relative active:scale-[0.98]">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-blue-500/20 border border-blue-500/30 group-hover:bg-blue-500/30 transition-colors">
              <Link2 className="w-3.5 h-3.5 text-blue-300" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white group-hover:text-blue-300 transition-colors">
                {entity.name}
              </h4>
              <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-black">
                {entity.type}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`px-2 py-0.5 rounded-full text-[9px] font-black border ${
              entity.status === 'active' ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
            }`}>
              {entity.status.toUpperCase()}
            </div>
            <ExternalLink className="w-3 h-3 text-white/20 group-hover:text-blue-400 transition-colors" />
          </div>
        </div>

        <p className="text-xs text-foreground/90 leading-relaxed line-clamp-3 italic">
          &ldquo;{entity.summary}&rdquo;
        </p>

        {entity.tags && (
          <div className="grid grid-cols-2 gap-4 pt-1 border-t border-white/5 mt-2">
            {entity.tags.what && (Array.isArray(entity.tags.what) ? entity.tags.what : []).length > 0 && (
              <div className="space-y-1">
                <span className="text-[9px] font-black text-blue-400/80 uppercase tracking-widest">What</span>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(entity.tags.what) ? entity.tags.what : []).slice(0, 2).map((t: string, i: number) => (
                    <span key={i} className="text-[10px] text-foreground font-medium">{t}</span>
                  ))}
                </div>
              </div>
            )}
            {entity.owner && (
              <div className="space-y-1">
                <span className="text-[9px] font-black text-indigo-400/80 uppercase tracking-widest">Owner</span>
                <div className="text-[10px] text-foreground font-medium">{entity.owner}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

/** Inline editable text field */
function InlineTextField({
  value,
  onSave,
  placeholder,
  multiline = false,
}: {
  value: string;
  onSave: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  if (!editing) {
    return (
      <div
        onClick={() => setEditing(true)}
        className="cursor-text hover:bg-white/5 rounded px-1 -mx-1 transition-colors"
        title="點擊編輯"
      >
        {value || <span className="text-muted-foreground italic">{placeholder || "點擊編輯"}</span>}
      </div>
    );
  }

  if (multiline) {
    return (
      <div className="space-y-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoFocus
          rows={4}
          className="w-full px-3 py-2 text-sm bg-background border border-primary/50 rounded-lg text-foreground focus:outline-none resize-none"
        />
        <div className="flex gap-2">
          <button
            onClick={() => { onSave(draft); setEditing(false); }}
            className="px-3 py-1 text-xs font-bold bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            儲存
          </button>
          <button
            onClick={() => { setDraft(value); setEditing(false); }}
            className="px-3 py-1 text-xs font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary"
          >
            取消
          </button>
        </div>
      </div>
    );
  }

  return (
    <input
      type="text"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      autoFocus
      onBlur={() => { onSave(draft); setEditing(false); }}
      onKeyDown={(e) => {
        if (e.key === "Enter") { onSave(draft); setEditing(false); }
        if (e.key === "Escape") { setDraft(value); setEditing(false); }
      }}
      className="w-full px-2 py-1 text-sm bg-background border border-primary/50 rounded text-foreground focus:outline-none"
    />
  );
}

export function TaskDetailDrawer({
  task,
  onClose,
  entityNames = {},
  entitiesById = {},
  onTaskUpdated,
  onUpdateTask,
  onConfirmTask,
}: TaskDetailDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [localTask, setLocalTask] = useState<Task | null>(task);
  const { user, partner } = useAuth();
  const [authToken, setAuthToken] = useState<string | null>(null);

  // Cancel confirm dialog state
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  // Reject reason state
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  // Status dropdown
  const [showStatusDropdown, setShowStatusDropdown] = useState(false);
  // Warning dialog state
  const [pendingStatusChange, setPendingStatusChange] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  // Comments state
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [newComment, setNewComment] = useState("");
  const [commentSubmitting, setCommentSubmitting] = useState(false);

  useEffect(() => {
    setLocalTask(task);
    setShowCancelConfirm(false);
    setShowRejectInput(false);
    setRejectReason("");
    setShowStatusDropdown(false);
    setPendingStatusChange(null);
    setWarningMessage(null);
    setComments([]);
    setCommentsError(null);
    setNewComment("");
  }, [task]);

  // Fetch comments when task and token are available
  useEffect(() => {
    if (!task?.id || !authToken) return;
    getTaskComments(authToken, task.id)
      .then(setComments)
      .catch(() => setCommentsError("無法載入留言"));
  }, [task?.id, authToken]);

  const handleCommentSubmit = async () => {
    const content = newComment.trim();
    if (!content || !authToken || !localTask) return;
    setCommentSubmitting(true);
    try {
      const created = await createTaskComment(authToken, localTask.id, content);
      setComments((prev) => [...prev, created]);
      setNewComment("");
    } catch {
      // Do not clear input on failure so user can retry
    } finally {
      setCommentSubmitting(false);
    }
  };

  const handleCommentDelete = async (commentId: string) => {
    if (!authToken || !localTask) return;
    try {
      await deleteTaskComment(authToken, localTask.id, commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
    } catch {
      // Silent failure — comment remains visible, user can retry
    }
  };

  useEffect(() => {
    if (user) {
      user.getIdToken().then(setAuthToken).catch(() => setAuthToken(null));
    } else {
      setAuthToken(null);
    }
  }, [user]);

  const handleAttachmentsChanged = useCallback(
    (attachments: Task["attachments"]) => {
      if (localTask) {
        setLocalTask({ ...localTask, attachments });
      }
      onTaskUpdated?.();
    },
    [localTask, onTaskUpdated]
  );

  useEffect(() => {
    if (task) {
      setIsVisible(true);
      document.body.style.overflow = "hidden";
    } else {
      setIsVisible(false);
      document.body.style.overflow = "unset";
    }
  }, [task]);

  const handleFieldSave = useCallback(async (field: string, value: unknown) => {
    if (!localTask || !onUpdateTask) return;
    const prev = localTask;
    setLocalTask({ ...localTask, [field]: value });
    try {
      await onUpdateTask(localTask.id, { [field]: value });
    } catch {
      setLocalTask(prev);
    }
  }, [localTask, onUpdateTask]);

  function requestStatusChange(newStatus: string) {
    if (!localTask) return;
    setShowStatusDropdown(false);

    // Warning: skipping todo → done directly
    if (localTask.status === "todo" && newStatus === "done") {
      setWarningMessage("建議先經過 in_progress 和 review，確定要直接完成？");
      setPendingStatusChange(newStatus);
      return;
    }
    // Warning: moving to review with no result
    if (newStatus === "review" && !localTask.result) {
      setWarningMessage("建議填寫任務成果後再送審，確定要送審？");
      setPendingStatusChange(newStatus);
      return;
    }
    applyStatusChange(newStatus);
  }

  function applyStatusChange(newStatus: string) {
    if (!localTask || !onUpdateTask) return;
    const prev = localTask;
    setLocalTask({ ...localTask, status: newStatus as Task["status"] });
    setPendingStatusChange(null);
    setWarningMessage(null);
    onUpdateTask(localTask.id, { status: newStatus }).catch(() => setLocalTask(prev));
  }

  const currentUserId = partner?.id;
  const canCancel = localTask && (
    currentUserId === localTask.assignee ||
    currentUserId === localTask.createdBy
  );

  if (!task) return null;

  const availableTransitions = STATUS_TRANSITIONS[localTask?.status ?? task.status] ?? [];
  const displayTask = localTask ?? task;

  return (
    <div
      className={`fixed inset-0 z-50 transition-opacity duration-300 ${
        isVisible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/85 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`absolute right-0 top-0 bottom-0 w-full max-w-2xl bg-gradient-to-b from-[#0d0d0d] to-[#050505] border-l border-white/10 shadow-2xl transition-transform duration-500 ease-out flex flex-col ${
          isVisible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header Section */}
        <div className="p-6 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-start justify-between mb-6">
            <div className="space-y-4 flex-1 pr-8">
              <div className="flex flex-wrap items-center gap-2.5">
                {/* Status badge with dropdown */}
                <div className="relative">
                  <button
                    onClick={() => setShowStatusDropdown(!showStatusDropdown)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border transition-colors ${statusColors[displayTask.status]} ${onUpdateTask && availableTransitions.length > 0 ? "hover:opacity-80 cursor-pointer" : "cursor-default"}`}
                  >
                    {displayTask.status}
                    {onUpdateTask && availableTransitions.length > 0 && (
                      <ChevronDown className="w-3 h-3" />
                    )}
                  </button>
                  {showStatusDropdown && availableTransitions.length > 0 && (
                    <div className="absolute top-full mt-1 left-0 z-10 bg-card border border-border rounded-lg shadow-xl min-w-[140px] py-1">
                      {availableTransitions.map((s) => (
                        <button
                          key={s}
                          onClick={() => requestStatusChange(s)}
                          className="w-full text-left px-3 py-1.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${priorityBg[displayTask.priority]}`}>
                  {priorityIcons[displayTask.priority]}
                  {displayTask.priority}
                </span>
                {displayTask.planId && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border border-purple-500/30 bg-purple-500/10 text-purple-300 shadow-sm">
                    <Layers className="w-3.5 h-3.5" />
                    {entityNames[displayTask.planId] || displayTask.planId}
                    {displayTask.planOrder !== null && (
                      <span className="opacity-70 ml-1">#{displayTask.planOrder}</span>
                    )}
                  </span>
                )}
              </div>

              {/* Inline editable title */}
              <h2 className="text-2xl font-bold text-white leading-tight tracking-tight">
                {onUpdateTask ? (
                  <InlineTextField
                    value={displayTask.title}
                    onSave={(v) => handleFieldSave("title", v)}
                    placeholder="任務標題"
                  />
                ) : displayTask.title}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-white/10 text-muted-foreground hover:text-white transition-all border border-transparent hover:border-white/20"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Meta fields */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-2">
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <User className="w-3 h-3 text-indigo-400" /> Owner
              </span>
              {onUpdateTask ? (
                <div className="text-sm font-bold text-white">
                  <InlineTextField
                    value={displayTask.assigneeName || displayTask.assignee || ""}
                    onSave={(v) => handleFieldSave("assignee", v)}
                    placeholder="Unassigned"
                  />
                </div>
              ) : (
                <div className="text-sm font-bold text-white truncate">
                  {displayTask.assigneeName || displayTask.assignee || "Unassigned"}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <Clock className="w-3 h-3 text-orange-400" /> Due Date
              </span>
              {onUpdateTask ? (
                <input
                  type="date"
                  value={displayTask.dueDate ? displayTask.dueDate.toISOString().slice(0, 10) : ""}
                  onChange={(e) => handleFieldSave("due_date", e.target.value || null)}
                  className="text-sm font-bold text-white bg-transparent border-b border-transparent hover:border-white/20 focus:border-primary/50 focus:outline-none w-full"
                />
              ) : (
                <div className="text-sm font-bold text-white">
                  {formatDate(displayTask.dueDate)}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <Hash className="w-3 h-3 text-blue-400" /> Project
              </span>
              <div className="text-sm font-black text-blue-400 uppercase tracking-tight">
                {displayTask.project || "N/A"}
              </div>
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.15em] flex items-center gap-1.5 opacity-80">
                <Bot className="w-3 h-3 text-purple-400" /> Source
              </span>
              <div className="text-sm font-medium text-foreground/90 truncate">
                {displayTask.creatorName || displayTask.createdBy}
              </div>
            </div>
          </div>

          {/* Priority inline edit */}
          {onUpdateTask && (
            <div className="mt-4 pt-4 border-t border-white/5 flex items-center gap-3">
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-wide">優先級</span>
              <select
                value={displayTask.priority}
                onChange={(e) => handleFieldSave("priority", e.target.value)}
                className="text-xs bg-background border border-border rounded-md px-2 py-1 text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          )}
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar bg-black/20">
          <div className="p-8 space-y-10">

            {/* Context Cards Section */}
            {displayTask.linkedEntities.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-4 w-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Contextual Assets</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {displayTask.linkedEntities.map(id => (
                    <ContextCard key={id} name={id} entity={entitiesById[id]} />
                  ))}
                </div>
              </div>
            )}

            {/* Description Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <div className="h-4 w-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Instruction &amp; Logic</h3>
              </div>
              {onUpdateTask ? (
                <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-4 shadow-inner">
                  <InlineTextField
                    value={displayTask.description || ""}
                    onSave={(v) => handleFieldSave("description", v)}
                    placeholder="點擊新增描述"
                    multiline
                  />
                </div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none bg-white/[0.03] border border-white/10 rounded-2xl p-6 shadow-inner leading-relaxed text-foreground">
                  <MarkdownRenderer content={displayTask.description || "_No description provided._"} />
                </div>
              )}
            </div>

            {/* Acceptance Criteria */}
            {displayTask.acceptanceCriteria && displayTask.acceptanceCriteria.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-4 w-1.5 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)]" />
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Success Criteria</h3>
                </div>
                <div className="space-y-3">
                  {displayTask.acceptanceCriteria.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-4 bg-white/[0.03] border border-white/10 p-4 rounded-xl hover:bg-white/[0.05] transition-colors">
                      <div className="mt-0.5 w-5 h-5 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center flex-shrink-0 text-[11px] font-black text-purple-300">
                        {idx + 1}
                      </div>
                      <p className="text-sm text-foreground leading-relaxed font-medium">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Attachments */}
            {localTask && authToken && (
              <div className="space-y-4">
                <TaskAttachments
                  task={localTask}
                  token={authToken}
                  onAttachmentsChanged={handleAttachmentsChanged}
                />
              </div>
            )}

            {/* Result / Deliverables */}
            {displayTask.result && (
              <div className="space-y-4 pt-4 border-t border-white/10">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-4 w-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">Outcome</h3>
                </div>
                <div className="bg-green-500/10 border border-green-500/20 rounded-2xl p-6 text-sm text-green-50 leading-relaxed italic shadow-inner">
                  <MarkdownRenderer content={displayTask.result} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        {(onUpdateTask || onConfirmTask) && (
          <div className="p-4 border-t border-white/10 bg-white/[0.01] space-y-3">

            {/* Cancel button (owner/creator only) */}
            {onUpdateTask && canCancel && displayTask.status !== "cancelled" && displayTask.status !== "done" && (
              <div>
                {!showCancelConfirm ? (
                  <button
                    onClick={() => setShowCancelConfirm(true)}
                    className="w-full px-4 py-2 text-sm font-bold text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/10 transition-colors"
                  >
                    取消任務
                  </button>
                ) : (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 space-y-2">
                    <p className="text-sm text-red-300">確定要取消此任務？</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setShowCancelConfirm(false);
                          handleFieldSave("status", "cancelled");
                        }}
                        className="px-3 py-1.5 text-xs font-bold bg-red-500 text-white rounded-md hover:bg-red-600"
                      >
                        確定取消
                      </button>
                      <button
                        onClick={() => setShowCancelConfirm(false)}
                        className="px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary"
                      >
                        返回
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Review: Approve / Reject */}
            {onConfirmTask && displayTask.status === "review" && (
              <div className="space-y-2">
                {!showRejectInput ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => onConfirmTask(displayTask.id, { action: "approve" })}
                      className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-bold bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                      <Check className="w-4 h-4" />
                      Approve
                    </button>
                    <button
                      onClick={() => setShowRejectInput(true)}
                      className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-bold border border-red-500/40 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
                    >
                      <X className="w-4 h-4" />
                      Reject
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="拒絕原因（選填）"
                      rows={2}
                      className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none resize-none"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          onConfirmTask(displayTask.id, {
                            action: "reject",
                            rejection_reason: rejectReason || undefined,
                          });
                          setShowRejectInput(false);
                          setRejectReason("");
                        }}
                        className="flex-1 px-3 py-1.5 text-xs font-bold bg-red-500 text-white rounded-md hover:bg-red-600"
                      >
                        確認拒絕
                      </button>
                      <button
                        onClick={() => { setShowRejectInput(false); setRejectReason(""); }}
                        className="px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Comments section */}
        <div className="p-4 border-t border-white/10 space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-4 w-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.4)]" />
            <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-white/90">留言</h3>
            <MessageSquare className="w-3.5 h-3.5 text-white/40" />
          </div>

          {commentsError ? (
            <p className="text-xs text-red-400">{commentsError}</p>
          ) : comments.length === 0 ? (
            <p className="text-xs text-muted-foreground">尚無留言</p>
          ) : (
            <div className="space-y-3">
              {comments.map((comment) => {
                const canDelete =
                  partner?.isAdmin || (partner && partner.id === comment.partnerId);
                return (
                  <div key={comment.id} className="flex gap-2.5 group">
                    <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                      <span className="text-[10px] font-bold text-blue-300">
                        {comment.authorName.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white/80">{comment.authorName}</span>
                          <span className="text-[10px] text-muted-foreground">
                            {comment.createdAt.toLocaleString("zh-TW")}
                          </span>
                        </div>
                        {canDelete && (
                          <button
                            onClick={() => handleCommentDelete(comment.id)}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-red-400/60 hover:text-red-400 transition-all"
                            title="刪除留言"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                      <p className="text-xs text-foreground/80 mt-0.5 leading-relaxed whitespace-pre-wrap">
                        {comment.content}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* New comment input */}
          <div className="space-y-2">
            <textarea
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="新增留言..."
              rows={2}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none resize-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleCommentSubmit();
                }
              }}
            />
            <button
              onClick={handleCommentSubmit}
              disabled={!newComment.trim() || commentSubmitting}
              className="px-3 py-1.5 text-xs font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {commentSubmitting ? "送出中..." : "送出留言"}
            </button>
          </div>
        </div>

        {/* Warning dialog */}
        {warningMessage && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-card border border-border rounded-2xl p-6 m-4 max-w-sm w-full space-y-4 shadow-2xl">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-foreground">{warningMessage}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => pendingStatusChange && applyStatusChange(pendingStatusChange)}
                  className="flex-1 px-3 py-2 text-xs font-bold bg-yellow-600 text-white rounded-lg hover:bg-yellow-700"
                >
                  強制執行
                </button>
                <button
                  onClick={() => { setPendingStatusChange(null); setWarningMessage(null); }}
                  className="flex-1 px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary"
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
