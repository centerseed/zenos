// ZenOS · TaskDetailDrawer — Zen Ink migration (B4)
// Replaces shadcn Sheet + Tailwind dark classes with zen/Drawer + zen primitives.
// headerExtras slot passed (null) for future Task L3 dispatcher badge / handoff tabs.
"use client";

import { useEffect, useState, useCallback } from "react";
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
  GitBranch,
  Send,
  CornerUpRight,
  X,
} from "lucide-react";
import { useInk } from "@/lib/zen-ink/tokens";
import { Drawer } from "./zen/Drawer";
import { Input } from "./zen/Input";
import { Textarea } from "./zen/Textarea";
import { Select } from "./zen/Select";
import { Btn } from "./zen/Btn";
import { Chip } from "./zen/Chip";
import { Dialog } from "./zen/Dialog";

interface TaskDetailDrawerProps {
  task: Task | null;
  onClose: () => void;
  entityNames?: Record<string, string>;
  entitiesById?: Record<string, Entity>;
  onTaskUpdated?: () => void;
  onUpdateTask?: (taskId: string, updates: Record<string, unknown>) => Promise<void>;
  onConfirmTask?: (taskId: string, data: { action: "approve" | "reject"; rejection_reason?: string }) => Promise<void>;
  onHandoffTask?: (
    taskId: string,
    data: { to_dispatcher: string; reason: string; output_ref?: string | null; notes?: string | null }
  ) => Promise<void>;
}

const DISPATCHER_PRESETS: Array<{ value: string; label: string }> = [
  { value: "agent:pm", label: "PM" },
  { value: "agent:architect", label: "Architect" },
  { value: "agent:developer", label: "Developer" },
  { value: "agent:qa", label: "QA" },
  { value: "agent:designer", label: "Designer" },
  { value: "agent:debugger", label: "Debugger" },
  { value: "human", label: "Human" },
];

function dispatcherLabel(value: string | null | undefined): string {
  if (!value) return "未指派";
  const preset = DISPATCHER_PRESETS.find((p) => p.value === value);
  return preset ? preset.label : value;
}

/** Map dispatcher value to Zen Chip tone */
function dispatcherChipTone(value: string | null | undefined): "muted" | "jade" | "ocher" | "accent" | "plain" {
  if (!value) return "muted";
  if (value.startsWith("human")) return "jade";
  if (value === "agent:qa") return "ocher";
  if (value === "agent:developer") return "ocher";
  if (value === "agent:architect") return "plain";
  if (value === "agent:pm") return "jade";
  return "muted";
}

/** Map status to Chip tone */
function statusChipTone(status: string): "muted" | "jade" | "ocher" | "accent" | "plain" {
  switch (status) {
    case "done": return "jade";
    case "review": return "ocher";
    case "in_progress": return "ocher";
    case "cancelled": return "muted";
    case "blocked": return "accent";
    default: return "plain"; // todo, backlog
  }
}

/** Map priority to Chip tone */
function priorityChipTone(priority: string): "muted" | "jade" | "ocher" | "accent" | "plain" {
  switch (priority) {
    case "critical": return "accent";
    case "high": return "ocher";
    case "medium": return "plain";
    case "low": return "muted";
    default: return "muted";
  }
}

const priorityIcons: Record<string, React.ReactNode> = {
  critical: <AlertTriangle style={{ width: 12, height: 12 }} />,
  high: <ArrowUp style={{ width: 12, height: 12 }} />,
  medium: <Minus style={{ width: 12, height: 12 }} />,
  low: <ArrowDown style={{ width: 12, height: 12 }} />,
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

function taskIdsToText(taskIds: string[] | undefined): string {
  return (taskIds ?? []).join(", ");
}

function criteriaToText(criteria: string[] | undefined): string {
  return (criteria ?? []).join("\n");
}

function prettyJson(value: unknown): string {
  if (!value || typeof value !== "object") return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
}

function applyLocalTaskFieldUpdate(task: Task, field: string, value: unknown): Task {
  switch (field) {
    case "due_date":
      return {
        ...task,
        dueDate: typeof value === "string" && value ? new Date(value) : null,
      };
    case "assignee_role_id":
      return { ...task, assigneeRoleId: typeof value === "string" ? value : null };
    case "plan_id":
      return { ...task, planId: typeof value === "string" ? value : null };
    case "plan_order":
      return { ...task, planOrder: typeof value === "number" ? value : null };
    case "depends_on_task_ids":
      return { ...task, dependsOnTaskIds: Array.isArray(value) ? value as string[] : [] };
    case "linked_protocol":
      return { ...task, linkedProtocol: typeof value === "string" ? value : null };
    case "linked_blindspot":
      return { ...task, linkedBlindspot: typeof value === "string" ? value : null };
    case "source_metadata":
      return { ...task, sourceMetadata: (value as Task["sourceMetadata"]) ?? undefined };
    case "blocked_by":
      return { ...task, blockedBy: Array.isArray(value) ? value as string[] : [] };
    case "blocked_reason":
      return { ...task, blockedReason: typeof value === "string" ? value : null };
    case "acceptance_criteria":
      return { ...task, acceptanceCriteria: Array.isArray(value) ? value as string[] : [] };
    case "parent_task_id":
      return { ...task, parentTaskId: typeof value === "string" ? value : null };
    case "dispatcher":
      return { ...task, dispatcher: typeof value === "string" ? value : null };
    default:
      return { ...task, [field]: value };
  }
}

function ContextCard({ entity }: { entity?: Entity; name: string }) {
  const t = useInk("light");
  const { c } = t;
  if (!entity) return null;

  return (
    <Link href={`/knowledge-map?id=${entity.id}`} style={{ display: "block", textDecoration: "none" }}>
      <div
        style={{
          background: c.surface,
          border: `1px solid ${c.inkHair}`,
          borderRadius: t.radius,
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          overflow: "hidden",
          cursor: "pointer",
          transition: "border-color 0.15s, background 0.15s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLDivElement).style.background = c.paperWarm;
          (e.currentTarget as HTMLDivElement).style.borderColor = c.inkHairBold;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLDivElement).style.background = c.surface;
          (e.currentTarget as HTMLDivElement).style.borderColor = c.inkHair;
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                padding: 6,
                borderRadius: t.radius,
                background: c.vermSoft,
                border: `1px solid ${c.vermLine}`,
                display: "flex",
                alignItems: "center",
              }}
            >
              <Link2 style={{ width: 14, height: 14, color: c.vermillion }} />
            </div>
            <div>
              <div style={{ fontFamily: t.fontBody, fontSize: 13, fontWeight: 600, color: c.ink, letterSpacing: "0.01em" }}>
                {entity.name}
              </div>
              <div style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint, textTransform: "uppercase", letterSpacing: "0.12em" }}>
                {entity.type}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Chip t={t} tone={entity.status === "active" ? "jade" : "ocher"}>
              {entity.status.toUpperCase()}
            </Chip>
            <ExternalLink style={{ width: 12, height: 12, color: c.inkFaint }} />
          </div>
        </div>
        <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.inkMuted, lineHeight: 1.6, margin: 0, fontStyle: "italic" }}>
          &ldquo;{entity.summary}&rdquo;
        </p>
        {entity.tags?.what && Array.isArray(entity.tags.what) && entity.tags.what.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, paddingTop: 8, borderTop: `1px solid ${c.inkHair}` }}>
            {(entity.tags.what as string[]).slice(0, 2).map((tag, i) => (
              <span key={i} style={{ fontFamily: t.fontBody, fontSize: 10, color: c.inkMuted }}>{tag}</span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}

/** Inline editable text field — Zen version */
function InlineTextField({
  value,
  onSave,
  placeholder,
  multiline = false,
  t,
}: {
  value: string;
  onSave: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
  t: ReturnType<typeof useInk>;
}) {
  const { c } = t;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  if (!editing) {
    return (
      <div
        onClick={() => setEditing(true)}
        style={{
          cursor: "text",
          padding: "2px 4px",
          margin: "0 -4px",
          borderRadius: t.radius,
          transition: "background 0.15s",
          color: value ? c.ink : c.inkFaint,
          fontStyle: value ? "normal" : "italic",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.background = c.paperWarm)}
        onMouseLeave={(e) => ((e.currentTarget as HTMLDivElement).style.background = "transparent")}
        title="點擊編輯"
      >
        {value || (placeholder || "點擊編輯")}
      </div>
    );
  }

  if (multiline) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <Textarea
          t={t}
          value={draft}
          onChange={setDraft}
          autoFocus
          rows={4}
          resize="vertical"
        />
        <div style={{ display: "flex", gap: 8 }}>
          <Btn t={t} variant="ink" size="sm" onClick={() => { onSave(draft); setEditing(false); }}>
            儲存
          </Btn>
          <Btn t={t} variant="ghost" size="sm" onClick={() => { setDraft(value); setEditing(false); }}>
            取消
          </Btn>
        </div>
      </div>
    );
  }

  return (
    <Input
      t={t}
      value={draft}
      onChange={setDraft}
      autoFocus
      onBlur={() => { onSave(draft); setEditing(false); }}
      onKeyDown={(e) => {
        if (e.key === "Enter") { onSave(draft); setEditing(false); }
        if (e.key === "Escape") { setDraft(value); setEditing(false); }
      }}
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
  onHandoffTask,
}: TaskDetailDrawerProps) {
  const t = useInk("light");
  const { c } = t;

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
  // Handoff form state
  const [showHandoffForm, setShowHandoffForm] = useState(false);
  const [handoffTarget, setHandoffTarget] = useState<string>("agent:developer");
  const [handoffCustom, setHandoffCustom] = useState("");
  const [handoffReason, setHandoffReason] = useState("");
  const [handoffNotes, setHandoffNotes] = useState("");
  const [handoffOutputRef, setHandoffOutputRef] = useState("");
  const [handoffSubmitting, setHandoffSubmitting] = useState(false);
  const [handoffError, setHandoffError] = useState<string | null>(null);
  const [advancedSubmitting, setAdvancedSubmitting] = useState(false);
  const [advancedError, setAdvancedError] = useState<string | null>(null);
  const [draftAcceptanceCriteria, setDraftAcceptanceCriteria] = useState("");
  const [draftAssigneeRoleId, setDraftAssigneeRoleId] = useState("");
  const [draftPlanId, setDraftPlanId] = useState("");
  const [draftPlanOrder, setDraftPlanOrder] = useState("");
  const [draftLinkedProtocol, setDraftLinkedProtocol] = useState("");
  const [draftLinkedBlindspot, setDraftLinkedBlindspot] = useState("");
  const [draftDependsOnTaskIds, setDraftDependsOnTaskIds] = useState("");
  const [draftBlockedBy, setDraftBlockedBy] = useState("");
  const [draftBlockedReason, setDraftBlockedReason] = useState("");
  const [draftParentTaskId, setDraftParentTaskId] = useState("");
  const [draftDispatcher, setDraftDispatcher] = useState("");
  const [draftSourceMetadata, setDraftSourceMetadata] = useState("");

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
    setShowHandoffForm(false);
    setHandoffReason("");
    setHandoffNotes("");
    setHandoffOutputRef("");
    setHandoffError(null);
    setHandoffCustom("");
    setHandoffTarget("agent:developer");
    setAdvancedSubmitting(false);
    setAdvancedError(null);
    setDraftAcceptanceCriteria(criteriaToText(task?.acceptanceCriteria));
    setDraftAssigneeRoleId(task?.assigneeRoleId ?? "");
    setDraftPlanId(task?.planId ?? "");
    setDraftPlanOrder(task?.planOrder?.toString() ?? "");
    setDraftLinkedProtocol(task?.linkedProtocol ?? "");
    setDraftLinkedBlindspot(task?.linkedBlindspot ?? "");
    setDraftDependsOnTaskIds(taskIdsToText(task?.dependsOnTaskIds));
    setDraftBlockedBy(taskIdsToText(task?.blockedBy));
    setDraftBlockedReason(task?.blockedReason ?? "");
    setDraftParentTaskId(task?.parentTaskId ?? "");
    setDraftDispatcher(task?.dispatcher ?? "");
    setDraftSourceMetadata(prettyJson(task?.sourceMetadata));
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

  const handleHandoffSubmit = useCallback(async () => {
    if (!localTask || !onHandoffTask) return;
    const to = handoffTarget === "__custom" ? handoffCustom.trim() : handoffTarget;
    if (!to) {
      setHandoffError("請選擇或輸入 dispatcher");
      return;
    }
    if (!handoffReason.trim()) {
      setHandoffError("reason 為必填");
      return;
    }
    setHandoffSubmitting(true);
    setHandoffError(null);
    try {
      await onHandoffTask(localTask.id, {
        to_dispatcher: to,
        reason: handoffReason.trim(),
        output_ref: handoffOutputRef.trim() || null,
        notes: handoffNotes.trim() || null,
      });
      setShowHandoffForm(false);
      setHandoffReason("");
      setHandoffNotes("");
      setHandoffOutputRef("");
      setHandoffCustom("");
    } catch (err) {
      setHandoffError(err instanceof Error ? err.message : "Handoff 失敗");
    } finally {
      setHandoffSubmitting(false);
    }
  }, [localTask, onHandoffTask, handoffTarget, handoffCustom, handoffReason, handoffOutputRef, handoffNotes]);

  const handleFieldSave = useCallback(async (field: string, value: unknown) => {
    if (!localTask || !onUpdateTask) return;
    const prev = localTask;
    setLocalTask(applyLocalTaskFieldUpdate(localTask, field, value));
    try {
      await onUpdateTask(localTask.id, { [field]: value });
    } catch {
      setLocalTask(prev);
    }
  }, [localTask, onUpdateTask]);

  const handleAdvancedSave = useCallback(async () => {
    if (!localTask || !onUpdateTask) return;

    const parseIds = (raw: string) =>
      raw.split(",").map((item) => item.trim()).filter(Boolean);
    const parseCriteria = (raw: string) =>
      raw.split("\n").map((item) => item.trim()).filter(Boolean);

    let parsedMetadata: Record<string, unknown> | null = null;
    if (draftSourceMetadata.trim()) {
      try {
        parsedMetadata = JSON.parse(draftSourceMetadata);
      } catch {
        setAdvancedError("source metadata 必須是合法 JSON");
        return;
      }
    }

    const updates: Record<string, unknown> = {
      acceptance_criteria: parseCriteria(draftAcceptanceCriteria),
      assignee_role_id: draftAssigneeRoleId.trim() || null,
      plan_id: draftPlanId.trim() || null,
      plan_order: draftPlanOrder.trim() ? Number(draftPlanOrder) : null,
      linked_protocol: draftLinkedProtocol.trim() || null,
      linked_blindspot: draftLinkedBlindspot.trim() || null,
      depends_on_task_ids: parseIds(draftDependsOnTaskIds),
      blocked_by: parseIds(draftBlockedBy),
      blocked_reason: draftBlockedReason.trim() || null,
      parent_task_id: draftParentTaskId.trim() || null,
      dispatcher: draftDispatcher.trim() || null,
      source_metadata: parsedMetadata,
    };

    const prev = localTask;
    let next = localTask;
    for (const [field, value] of Object.entries(updates)) {
      next = applyLocalTaskFieldUpdate(next, field, value);
    }

    setAdvancedSubmitting(true);
    setAdvancedError(null);
    setLocalTask(next);
    try {
      await onUpdateTask(localTask.id, updates);
    } catch (err) {
      setLocalTask(prev);
      setAdvancedError(err instanceof Error ? err.message : "Rich task 欄位更新失敗");
    } finally {
      setAdvancedSubmitting(false);
    }
  }, [
    draftAcceptanceCriteria,
    draftAssigneeRoleId,
    draftBlockedBy,
    draftBlockedReason,
    draftDependsOnTaskIds,
    draftDispatcher,
    draftLinkedBlindspot,
    draftLinkedProtocol,
    draftParentTaskId,
    draftPlanId,
    draftPlanOrder,
    draftSourceMetadata,
    localTask,
    onUpdateTask,
  ]);

  function requestStatusChange(newStatus: string) {
    if (!localTask) return;
    setShowStatusDropdown(false);

    if (localTask.status === "todo" && newStatus === "done") {
      setWarningMessage("建議先經過 in_progress 和 review，確定要直接完成？");
      setPendingStatusChange(newStatus);
      return;
    }
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

  // ── Section label style (shared) ─────────────────────────────────────────
  const sectionLabel = (label: string) => (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <div style={{ width: 3, height: 16, borderRadius: 999, background: c.vermillion, flexShrink: 0 }} />
      <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.16em", color: c.inkMuted }}>
        {label}
      </span>
    </div>
  );

  // ── Drawer header ─────────────────────────────────────────────────────────
  const drawerHeader = (
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Chips row */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
          {/* Status chip with dropdown */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setShowStatusDropdown(!showStatusDropdown)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "2px 8px",
                border: `1px solid ${c.inkHair}`,
                borderRadius: t.radius,
                background: "transparent",
                fontFamily: t.fontMono,
                fontSize: 10,
                fontWeight: 700,
                textTransform: "uppercase" as const,
                letterSpacing: "0.12em",
                color: statusChipTone(displayTask.status) === "jade" ? c.jade
                  : statusChipTone(displayTask.status) === "ocher" ? c.ocher
                  : statusChipTone(displayTask.status) === "accent" ? c.vermillion
                  : c.inkMuted,
                cursor: onUpdateTask && availableTransitions.length > 0 ? "pointer" : "default",
              }}
            >
              {displayTask.status}
              {onUpdateTask && availableTransitions.length > 0 && (
                <ChevronDown style={{ width: 10, height: 10 }} />
              )}
            </button>
            {showStatusDropdown && availableTransitions.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 4px)",
                  left: 0,
                  zIndex: 10,
                  background: c.surface,
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: t.radius,
                  boxShadow: "0 8px 24px rgba(58,52,44,0.10)",
                  minWidth: 140,
                  padding: "4px 0",
                }}
              >
                {availableTransitions.map((s) => (
                  <button
                    key={s}
                    onClick={() => requestStatusChange(s)}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      padding: "6px 12px",
                      fontFamily: t.fontBody,
                      fontSize: 12,
                      color: c.ink,
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      transition: "background 0.1s",
                    }}
                    onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = c.paperWarm)}
                    onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "transparent")}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Priority chip */}
          <Chip t={t} tone={priorityChipTone(displayTask.priority)} dot>
            {priorityIcons[displayTask.priority]}
            {displayTask.priority}
          </Chip>

          {/* Plan chip */}
          {displayTask.planId && (
            <Chip t={t} tone="ocher">
              <Layers style={{ width: 11, height: 11 }} />
              {entityNames[displayTask.planId] || displayTask.planId}
              {displayTask.planOrder !== null && (
                <span style={{ opacity: 0.7, marginLeft: 2 }}>#{displayTask.planOrder}</span>
              )}
            </Chip>
          )}

          {/* Dispatcher chip */}
          <Chip t={t} tone={dispatcherChipTone(displayTask.dispatcher)} style={{ cursor: "default" }}>
            <GitBranch style={{ width: 11, height: 11 }} />
            {dispatcherLabel(displayTask.dispatcher)}
          </Chip>

          {/* Subtask chip */}
          {displayTask.parentTaskId && (
            <Chip t={t} tone="muted" style={{ cursor: "default" }}>
              <CornerUpRight style={{ width: 11, height: 11 }} />
              Subtask
            </Chip>
          )}
        </div>

        {/* Inline editable title */}
        <div style={{ fontFamily: t.fontHead, fontSize: 20, fontWeight: 500, color: c.ink, letterSpacing: "0.01em", lineHeight: 1.3 }}>
          {onUpdateTask ? (
            <InlineTextField
              t={t}
              value={displayTask.title}
              onSave={(v) => handleFieldSave("title", v)}
              placeholder="任務標題"
            />
          ) : displayTask.title}
        </div>
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        aria-label="關閉"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 28,
          height: 28,
          border: `1px solid ${c.inkHair}`,
          borderRadius: t.radius,
          background: "transparent",
          color: c.inkMuted,
          cursor: "pointer",
          fontSize: 14,
          flexShrink: 0,
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = c.paperWarm)}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "transparent")}
      >
        <X style={{ width: 14, height: 14 }} />
      </button>
    </div>
  );

  // ── Drawer footer ─────────────────────────────────────────────────────────
  const drawerFooter = (onUpdateTask || onConfirmTask || onHandoffTask) ? (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
      {/* Handoff */}
      {onHandoffTask && displayTask.status !== "done" && displayTask.status !== "cancelled" && (
        <div>
          {!showHandoffForm ? (
            <Btn t={t} variant="outline" size="sm" onClick={() => setShowHandoffForm(true)} style={{ width: "100%", justifyContent: "center" }}>
              <GitBranch style={{ width: 13, height: 13 }} />
              交棒 Handoff
            </Btn>
          ) : (
            <div
              style={{
                background: c.paperWarm,
                border: `1px solid ${c.inkHair}`,
                borderRadius: t.radius,
                padding: 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkMuted, display: "flex", alignItems: "center", gap: 4 }}>
                <GitBranch style={{ width: 10, height: 10 }} /> Handoff to
              </span>
              <Select
                t={t}
                size="sm"
                value={handoffTarget}
                onChange={(v) => setHandoffTarget(v ?? "agent:developer")}
                options={[
                  ...DISPATCHER_PRESETS.map((p) => ({ value: p.value, label: `${p.label} (${p.value})` })),
                  { value: "__custom", label: "自訂…" },
                ]}
              />
              {handoffTarget === "__custom" && (
                <Input
                  t={t}
                  size="sm"
                  value={handoffCustom}
                  onChange={setHandoffCustom}
                  placeholder="e.g. human:barry 或 agent:xxx"
                />
              )}
              <Textarea
                t={t}
                size="sm"
                value={handoffReason}
                onChange={setHandoffReason}
                placeholder="交棒原因（必填）"
                rows={2}
                resize="none"
              />
              <Input
                t={t}
                size="sm"
                value={handoffOutputRef}
                onChange={setHandoffOutputRef}
                placeholder="output_ref（選填）"
              />
              <Textarea
                t={t}
                size="sm"
                value={handoffNotes}
                onChange={setHandoffNotes}
                placeholder="補充 notes（選填）"
                rows={2}
                resize="none"
              />
              {handoffError && (
                <p style={{ fontFamily: t.fontBody, fontSize: 11, color: c.vermillion, margin: 0 }}>{handoffError}</p>
              )}
              <div style={{ display: "flex", gap: 6 }}>
                <Btn
                  t={t}
                  variant="ink"
                  size="sm"
                  onClick={handleHandoffSubmit}
                  style={{ flex: 1, justifyContent: "center", opacity: handoffSubmitting ? 0.5 : 1 }}
                >
                  <Send style={{ width: 11, height: 11 }} />
                  {handoffSubmitting ? "送出中…" : "確認交棒"}
                </Btn>
                <Btn
                  t={t}
                  variant="ghost"
                  size="sm"
                  onClick={() => { setShowHandoffForm(false); setHandoffError(null); }}
                >
                  取消
                </Btn>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Cancel button */}
      {onUpdateTask && canCancel && displayTask.status !== "cancelled" && displayTask.status !== "done" && (
        <div>
          {!showCancelConfirm ? (
            <Btn t={t} variant="seal" size="sm" onClick={() => setShowCancelConfirm(true)} style={{ width: "100%", justifyContent: "center" }}>
              取消任務
            </Btn>
          ) : (
            <div
              style={{
                background: c.vermSoft,
                border: `1px solid ${c.vermLine}`,
                borderRadius: t.radius,
                padding: 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <p style={{ fontFamily: t.fontBody, fontSize: 13, color: c.vermillion, margin: 0 }}>確定要取消此任務？</p>
              <div style={{ display: "flex", gap: 6 }}>
                <Btn
                  t={t}
                  variant="seal"
                  size="sm"
                  onClick={() => { setShowCancelConfirm(false); handleFieldSave("status", "cancelled"); }}
                >
                  確定取消
                </Btn>
                <Btn t={t} variant="ghost" size="sm" onClick={() => setShowCancelConfirm(false)}>
                  返回
                </Btn>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Review: Approve / Reject */}
      {onConfirmTask && displayTask.status === "review" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {!showRejectInput ? (
            <div style={{ display: "flex", gap: 6 }}>
              <Btn
                t={t}
                variant="ink"
                size="sm"
                onClick={() => onConfirmTask(displayTask.id, { action: "approve" })}
                style={{ flex: 1, justifyContent: "center", background: c.jade }}
              >
                <Check style={{ width: 13, height: 13 }} />
                Approve
              </Btn>
              <Btn
                t={t}
                variant="outline"
                size="sm"
                onClick={() => setShowRejectInput(true)}
                style={{ flex: 1, justifyContent: "center", color: c.vermillion, borderColor: c.vermLine }}
              >
                Reject
              </Btn>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Textarea
                t={t}
                size="sm"
                value={rejectReason}
                onChange={setRejectReason}
                placeholder="拒絕原因（選填）"
                rows={2}
                resize="none"
              />
              <div style={{ display: "flex", gap: 6 }}>
                <Btn
                  t={t}
                  variant="seal"
                  size="sm"
                  onClick={() => {
                    onConfirmTask(displayTask.id, { action: "reject", rejection_reason: rejectReason || undefined });
                    setShowRejectInput(false);
                    setRejectReason("");
                  }}
                  style={{ flex: 1, justifyContent: "center" }}
                >
                  確認拒絕
                </Btn>
                <Btn t={t} variant="ghost" size="sm" onClick={() => { setShowRejectInput(false); setRejectReason(""); }}>
                  取消
                </Btn>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  ) : null;

  // ── Drawer body ───────────────────────────────────────────────────────────
  const drawerBody = (
    <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>

      {/* Meta fields */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Owner */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.12em", color: c.inkFaint, display: "flex", alignItems: "center", gap: 4 }}>
            <User style={{ width: 10, height: 10 }} /> Owner
          </span>
          {onUpdateTask ? (
            <InlineTextField
              t={t}
              value={displayTask.assigneeName || displayTask.assignee || ""}
              onSave={(v) => handleFieldSave("assignee", v)}
              placeholder="Unassigned"
            />
          ) : (
            <span style={{ fontFamily: t.fontBody, fontSize: 13, fontWeight: 500, color: c.ink }}>
              {displayTask.assigneeName || displayTask.assignee || "Unassigned"}
            </span>
          )}
        </div>

        {/* Due Date */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.12em", color: c.inkFaint, display: "flex", alignItems: "center", gap: 4 }}>
            <Clock style={{ width: 10, height: 10 }} /> Due Date
          </span>
          {onUpdateTask ? (
            <Input
              t={t}
              size="sm"
              type="date"
              value={displayTask.dueDate ? displayTask.dueDate.toISOString().slice(0, 10) : ""}
              onChange={(v) => handleFieldSave("due_date", v || null)}
            />
          ) : (
            <span style={{ fontFamily: t.fontBody, fontSize: 13, fontWeight: 500, color: c.ink }}>
              {formatDate(displayTask.dueDate)}
            </span>
          )}
        </div>

        {/* Project */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.12em", color: c.inkFaint, display: "flex", alignItems: "center", gap: 4 }}>
            <Hash style={{ width: 10, height: 10 }} /> Project
          </span>
          <span style={{ fontFamily: t.fontMono, fontSize: 12, fontWeight: 700, color: c.ocher, textTransform: "uppercase" as const }}>
            {displayTask.project || "N/A"}
          </span>
        </div>

        {/* Source */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.12em", color: c.inkFaint, display: "flex", alignItems: "center", gap: 4 }}>
            <Bot style={{ width: 10, height: 10 }} /> Source
          </span>
          <span style={{ fontFamily: t.fontBody, fontSize: 13, color: c.inkMuted }}>
            {displayTask.creatorName || displayTask.createdBy}
          </span>
        </div>
      </div>

      {/* Priority inline edit */}
      {onUpdateTask && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, paddingTop: 12, borderTop: `1px solid ${c.inkHair}` }}>
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.1em", color: c.inkFaint }}>優先級</span>
          <Select
            t={t}
            size="sm"
            value={displayTask.priority}
            onChange={(v) => v && handleFieldSave("priority", v)}
            options={[
              { value: "critical", label: "Critical", tone: "accent" },
              { value: "high", label: "High", tone: "ocher" },
              { value: "medium", label: "Medium" },
              { value: "low", label: "Low", tone: "muted" },
            ]}
            style={{ maxWidth: 160 }}
          />
        </div>
      )}

      {/* Context Cards */}
      {displayTask.linkedEntities.length > 0 && (
        <div>
          {sectionLabel("Contextual Assets")}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {displayTask.linkedEntities.map((id) => (
              <ContextCard key={id} name={id} entity={entitiesById[id]} />
            ))}
          </div>
        </div>
      )}

      {/* Description */}
      <div>
        {sectionLabel("Instruction & Logic")}
        {onUpdateTask ? (
          <div
            style={{
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              borderRadius: t.radius,
              padding: 16,
            }}
          >
            <InlineTextField
              t={t}
              value={displayTask.description || ""}
              onSave={(v) => handleFieldSave("description", v)}
              placeholder="點擊新增描述"
              multiline
            />
          </div>
        ) : (
          <div
            style={{
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              borderRadius: t.radius,
              padding: 24,
              fontFamily: t.fontBody,
              fontSize: 13,
              lineHeight: 1.7,
              color: c.ink,
            }}
          >
            <MarkdownRenderer content={displayTask.description || "_No description provided._"} />
          </div>
        )}
      </div>

      {/* Acceptance Criteria */}
      {(onUpdateTask || (displayTask.acceptanceCriteria && displayTask.acceptanceCriteria.length > 0)) && (
        <div>
          {sectionLabel("Success Criteria")}
          {onUpdateTask ? (
            <Textarea
              t={t}
              value={draftAcceptanceCriteria}
              onChange={setDraftAcceptanceCriteria}
              placeholder="每行一條 acceptance criteria"
              rows={4}
              resize="vertical"
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {displayTask.acceptanceCriteria.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 12,
                    background: c.paperWarm,
                    border: `1px solid ${c.inkHair}`,
                    borderRadius: t.radius,
                    padding: 12,
                  }}
                >
                  <div
                    style={{
                      flexShrink: 0,
                      width: 18,
                      height: 18,
                      borderRadius: "50%",
                      border: `1px solid ${c.inkHairBold}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: t.fontMono,
                      fontSize: 10,
                      fontWeight: 700,
                      color: c.inkMuted,
                      marginTop: 1,
                    }}
                  >
                    {idx + 1}
                  </div>
                  <p style={{ fontFamily: t.fontBody, fontSize: 13, color: c.ink, lineHeight: 1.6, margin: 0 }}>{item}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {(onUpdateTask || displayTask.assigneeRoleId || displayTask.linkedProtocol || displayTask.linkedBlindspot || displayTask.dependsOnTaskIds?.length || displayTask.blockedBy.length || displayTask.blockedReason || displayTask.sourceMetadata || displayTask.parentTaskId || displayTask.dispatcher || displayTask.planId) && (
        <div style={{ paddingTop: 16, borderTop: `1px solid ${c.inkHair}` }}>
          {sectionLabel("Rich Task Context")}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Assignee Role
              </span>
              {onUpdateTask ? (
                <Select
                  t={t}
                  size="sm"
                  value={draftAssigneeRoleId}
                  onChange={(value) => setDraftAssigneeRoleId(value ?? "")}
                  options={[
                    { value: "", label: "未指定" },
                    ...Object.values(entitiesById)
                      .filter((entity) => entity.type === "role")
                      .map((entity) => ({ value: entity.id, label: entity.name })),
                  ]}
                />
              ) : (
                <span style={{ fontFamily: t.fontBody, fontSize: 13, color: c.ink }}>
                  {displayTask.assigneeRoleId ? entityNames[displayTask.assigneeRoleId] ?? displayTask.assigneeRoleId : "未指定"}
                </span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Dispatcher
              </span>
              {onUpdateTask ? (
                <Select
                  t={t}
                  size="sm"
                  value={draftDispatcher}
                  onChange={(value) => setDraftDispatcher(value ?? "")}
                  options={[
                    { value: "", label: "未指定" },
                    ...DISPATCHER_PRESETS.map((preset) => ({
                      value: preset.value,
                      label: `${preset.label} (${preset.value})`,
                    })),
                  ]}
                />
              ) : (
                <span style={{ fontFamily: t.fontBody, fontSize: 13, color: c.ink }}>
                  {dispatcherLabel(displayTask.dispatcher)}
                </span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Plan ID
              </span>
              {onUpdateTask ? (
                <Input t={t} size="sm" value={draftPlanId} onChange={setDraftPlanId} placeholder="plan_id" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted }}>{displayTask.planId || "未指定"}</span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Plan Order
              </span>
              {onUpdateTask ? (
                <Input t={t} size="sm" type="number" value={draftPlanOrder} onChange={setDraftPlanOrder} placeholder="1" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted }}>{displayTask.planOrder ?? "未指定"}</span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Parent Task
              </span>
              {onUpdateTask ? (
                <Input t={t} size="sm" value={draftParentTaskId} onChange={setDraftParentTaskId} placeholder="parent_task_id" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted }}>{displayTask.parentTaskId || "未指定"}</span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Linked Protocol
              </span>
              {onUpdateTask ? (
                <Input t={t} size="sm" value={draftLinkedProtocol} onChange={setDraftLinkedProtocol} placeholder="protocol id" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted }}>{displayTask.linkedProtocol || "未指定"}</span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Linked Blindspot
              </span>
              {onUpdateTask ? (
                <Input t={t} size="sm" value={draftLinkedBlindspot} onChange={setDraftLinkedBlindspot} placeholder="blindspot id" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted }}>{displayTask.linkedBlindspot || "未指定"}</span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Depends On
              </span>
              {onUpdateTask ? (
                <Textarea t={t} value={draftDependsOnTaskIds} onChange={setDraftDependsOnTaskIds} rows={3} resize="vertical" placeholder="task-a, task-b" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted, whiteSpace: "pre-wrap" }}>{taskIdsToText(displayTask.dependsOnTaskIds) || "未指定"}</span>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Blocked By
              </span>
              {onUpdateTask ? (
                <Textarea t={t} value={draftBlockedBy} onChange={setDraftBlockedBy} rows={3} resize="vertical" placeholder="task-a, task-b" />
              ) : (
                <span style={{ fontFamily: t.fontMono, fontSize: 12, color: c.inkMuted, whiteSpace: "pre-wrap" }}>{taskIdsToText(displayTask.blockedBy) || "未指定"}</span>
              )}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Blocked Reason
              </span>
              {onUpdateTask ? (
                <Textarea t={t} value={draftBlockedReason} onChange={setDraftBlockedReason} rows={2} resize="vertical" placeholder="blocked_reason" />
              ) : (
                <div style={{ fontFamily: t.fontBody, fontSize: 13, color: c.inkMuted, lineHeight: 1.6 }}>{displayTask.blockedReason || "未指定"}</div>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: c.inkFaint }}>
                Source Metadata
              </span>
              {onUpdateTask ? (
                <Textarea
                  t={t}
                  value={draftSourceMetadata}
                  onChange={setDraftSourceMetadata}
                  rows={8}
                  resize="vertical"
                  placeholder='{"provenance":[{"type":"chat","label":"..."}]}'
                />
              ) : (
                <pre
                  style={{
                    margin: 0,
                    padding: 16,
                    background: c.paperWarm,
                    border: `1px solid ${c.inkHair}`,
                    borderRadius: t.radius,
                    fontFamily: t.fontMono,
                    fontSize: 11,
                    lineHeight: 1.6,
                    color: c.inkMuted,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {prettyJson(displayTask.sourceMetadata) || "未指定"}
                </pre>
              )}
            </div>

            {onUpdateTask && (
              <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between" }}>
                {advancedError ? (
                  <span style={{ fontFamily: t.fontBody, fontSize: 12, color: c.vermillion }}>{advancedError}</span>
                ) : (
                  <span style={{ fontFamily: t.fontBody, fontSize: 12, color: c.inkFaint }}>
                    這一區會一次更新 richer task 欄位。
                  </span>
                )}
                <Btn
                  t={t}
                  variant="ink"
                  size="sm"
                  onClick={handleAdvancedSave}
                  style={{ opacity: advancedSubmitting ? 0.5 : 1 }}
                >
                  {advancedSubmitting ? "儲存中…" : "儲存 Rich Fields"}
                </Btn>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Attachments */}
      {localTask && authToken && (
        <div>
          <TaskAttachments
            task={localTask}
            token={authToken}
            onAttachmentsChanged={handleAttachmentsChanged}
          />
        </div>
      )}

      {/* Handoff Timeline */}
      {displayTask.handoffEvents && displayTask.handoffEvents.length > 0 && (
        <div>
          {sectionLabel("Handoff Chain")}
          <ol style={{ listStyle: "none", margin: 0, padding: 0, borderLeft: `2px solid ${c.inkHair}`, marginLeft: 8, display: "flex", flexDirection: "column", gap: 0 }}>
            {displayTask.handoffEvents.map((event, idx) => {
              const at = new Date(event.at);
              const fromLabel = dispatcherLabel(event.fromDispatcher);
              const toLabel = dispatcherLabel(event.toDispatcher);
              return (
                <li key={idx} style={{ position: "relative", paddingLeft: 20, paddingBottom: idx < displayTask.handoffEvents!.length - 1 ? 16 : 0 }}>
                  <span
                    style={{
                      position: "absolute",
                      left: -7,
                      top: 4,
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      border: `2px solid ${c.inkHairBold}`,
                      background: c.surface,
                    }}
                  />
                  <div
                    style={{
                      background: c.paperWarm,
                      border: `1px solid ${c.inkHair}`,
                      borderRadius: t.radius,
                      padding: 10,
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <Chip t={t} tone={dispatcherChipTone(event.fromDispatcher)}>{fromLabel}</Chip>
                      <CornerUpRight style={{ width: 10, height: 10, color: c.inkFaint }} />
                      <Chip t={t} tone={dispatcherChipTone(event.toDispatcher)}>{toLabel}</Chip>
                      <span style={{ marginLeft: "auto", fontFamily: t.fontMono, fontSize: 9, color: c.inkFaint }}>
                        {at.toLocaleString("zh-TW", { hour12: false })}
                      </span>
                    </div>
                    <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.ink, lineHeight: 1.6, margin: 0 }}>{event.reason}</p>
                    {event.outputRef && (
                      <p style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkMuted, margin: 0, wordBreak: "break-all" }}>↳ {event.outputRef}</p>
                    )}
                    {event.notes && (
                      <p style={{ fontFamily: t.fontBody, fontSize: 10, color: c.inkFaint, lineHeight: 1.6, whiteSpace: "pre-wrap", margin: 0 }}>{event.notes}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}

      {/* Result / Outcome */}
      {displayTask.result && (
        <div style={{ paddingTop: 16, borderTop: `1px solid ${c.inkHair}` }}>
          {sectionLabel("Outcome")}
          <div
            style={{
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              borderRadius: t.radius,
              padding: 20,
              fontFamily: t.fontBody,
              fontSize: 13,
              lineHeight: 1.7,
              color: c.jade,
              fontStyle: "italic",
            }}
          >
            <MarkdownRenderer content={displayTask.result} />
          </div>
        </div>
      )}

      {/* Comments */}
      <div style={{ paddingTop: 16, borderTop: `1px solid ${c.inkHair}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 16, borderRadius: 999, background: c.inkHairBold, flexShrink: 0 }} />
          <span style={{ fontFamily: t.fontMono, fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: "0.16em", color: c.inkMuted }}>
            留言
          </span>
          <MessageSquare style={{ width: 11, height: 11, color: c.inkFaint }} />
        </div>

        {commentsError ? (
          <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.vermillion }}>{commentsError}</p>
        ) : comments.length === 0 ? (
          <p style={{ fontFamily: t.fontBody, fontSize: 12, color: c.inkFaint }}>尚無留言</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            {comments.map((comment) => {
              const canDelete = partner?.isAdmin || (partner && partner.id === comment.partnerId);
              return (
                <div key={comment.id} style={{ display: "flex", gap: 10 }}>
                  <div
                    style={{
                      flexShrink: 0,
                      width: 26,
                      height: 26,
                      borderRadius: "50%",
                      background: c.paperWarm,
                      border: `1px solid ${c.inkHair}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: t.fontMono,
                      fontSize: 10,
                      fontWeight: 700,
                      color: c.inkMuted,
                    }}
                  >
                    {comment.authorName.charAt(0).toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontFamily: t.fontBody, fontSize: 12, fontWeight: 600, color: c.ink }}>{comment.authorName}</span>
                        <span style={{ fontFamily: t.fontMono, fontSize: 10, color: c.inkFaint }}>
                          {comment.createdAt.toLocaleString("zh-TW")}
                        </span>
                      </div>
                      {canDelete && (
                        <button
                          onClick={() => handleCommentDelete(comment.id)}
                          title="刪除留言"
                          style={{
                            padding: 4,
                            borderRadius: t.radius,
                            border: "none",
                            background: "transparent",
                            color: c.inkFaint,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            transition: "color 0.15s, background 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.color = c.vermillion;
                            (e.currentTarget as HTMLButtonElement).style.background = c.vermSoft;
                          }}
                          onMouseLeave={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.color = c.inkFaint;
                            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                          }}
                        >
                          <Trash2 style={{ width: 11, height: 11 }} />
                        </button>
                      )}
                    </div>
                    <p style={{ fontFamily: t.fontBody, fontSize: 13, color: c.inkMuted, lineHeight: 1.6, margin: 0, whiteSpace: "pre-wrap" }}>
                      {comment.content}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* New comment */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Textarea
            t={t}
            value={newComment}
            onChange={setNewComment}
            placeholder="新增留言..."
            rows={2}
            resize="none"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleCommentSubmit();
              }
            }}
          />
          <Btn
            t={t}
            variant="ink"
            size="sm"
            onClick={handleCommentSubmit}
            style={{ opacity: !newComment.trim() || commentSubmitting ? 0.4 : 1, cursor: !newComment.trim() || commentSubmitting ? "not-allowed" : "pointer" }}
          >
            {commentSubmitting ? "送出中..." : "送出留言"}
          </Btn>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <Drawer
        t={t}
        open={!!task}
        onOpenChange={(open) => { if (!open) onClose(); }}
        side="right"
        width={600}
        header={drawerHeader}
        footer={drawerFooter}
        headerExtras={null}
      >
        {drawerBody}
      </Drawer>

      {/* Warning Dialog — status change confirmation */}
      <Dialog
        t={t}
        open={!!warningMessage}
        onOpenChange={(open) => { if (!open) { setPendingStatusChange(null); setWarningMessage(null); } }}
        title={
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <AlertTriangle style={{ width: 16, height: 16, color: c.ocher }} />
            確認狀態變更
          </span>
        }
        size="sm"
        footer={
          <>
            <Btn t={t} variant="ghost" size="sm" onClick={() => { setPendingStatusChange(null); setWarningMessage(null); }}>
              取消
            </Btn>
            <Btn
              t={t}
              variant="outline"
              size="sm"
              onClick={() => pendingStatusChange && applyStatusChange(pendingStatusChange)}
              style={{ color: c.ocher, borderColor: c.ocher }}
            >
              強制執行
            </Btn>
          </>
        }
      >
        <p style={{ fontFamily: t.fontBody, fontSize: 13, color: c.ink, lineHeight: 1.6, margin: 0 }}>{warningMessage}</p>
      </Dialog>
    </>
  );
}
