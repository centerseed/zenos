"use client";

import { useEffect, useRef, useState } from "react";
import type { Entity, Task } from "@/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import {
  AlertTriangle,
  ArrowUp,
  Minus,
  ArrowDown,
  X,
} from "lucide-react";

interface TaskDetailDrawerProps {
  task: Task | null;
  onClose: () => void;
  entityNames?: Record<string, string>;
  entitiesById?: Record<string, Entity>;
}

const priorityConfig: Record<
  string,
  { icon: React.ReactNode; label: string; color: string }
> = {
  critical: {
    icon: <AlertTriangle className="w-4 h-4" />,
    label: "Critical",
    color: "text-red-400",
  },
  high: {
    icon: <ArrowUp className="w-4 h-4" />,
    label: "High",
    color: "text-orange-400",
  },
  medium: {
    icon: <Minus className="w-4 h-4" />,
    label: "Medium",
    color: "text-blue-400",
  },
  low: {
    icon: <ArrowDown className="w-4 h-4" />,
    label: "Low",
    color: "text-muted-foreground",
  },
};

const statusColors: Record<string, string> = {
  backlog: "bg-secondary text-secondary-foreground",
  todo: "bg-blue-900/50 text-blue-400",
  in_progress: "bg-yellow-900/50 text-yellow-400",
  review: "bg-purple-900/50 text-purple-400",
  blocked: "bg-red-900/50 text-red-400",
  done: "bg-green-900/50 text-green-400",
  cancelled: "bg-secondary text-muted-foreground line-through",
  archived: "bg-secondary text-muted-foreground",
};

function formatDate(date: Date | null): string | null {
  if (!date) return null;
  return date.toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function TaskDetailDrawer({
  task,
  onClose,
  entityNames = {},
  entitiesById = {},
}: TaskDetailDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const [showProvenance, setShowProvenance] = useState(false);

  useEffect(() => {
    function handleEsc(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (task) {
      document.addEventListener("keydown", handleEsc);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "";
    };
  }, [task, onClose]);

  useEffect(() => {
    if (!task) setShowProvenance(false);
  }, [task]);

  if (!task) return null;

  const priority = priorityConfig[task.priority];
  const provenanceItems = Array.isArray(task.sourceMetadata?.provenance)
    ? task.sourceMetadata?.provenance
    : [];
  const syncSources = Array.isArray(task.sourceMetadata?.sync_sources)
    ? task.sourceMetadata?.sync_sources
    : [];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed right-0 top-0 h-full w-full max-w-2xl bg-card border-l border-border z-50 overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-300"
        role="dialog"
        aria-modal="true"
        aria-label={`Task detail: ${task.title}`}
      >
        {/* Header */}
        <div className="sticky top-0 bg-card/95 backdrop-blur-md border-b border-border px-6 py-4 z-10">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-foreground leading-tight">
                {task.title}
              </h2>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {/* Status Badge */}
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${statusColors[task.status] ?? "bg-secondary text-muted-foreground"}`}
                >
                  {task.status.replace("_", " ")}
                </span>

                {/* Priority with Icon */}
                {priority && (
                  <span
                    className={`inline-flex items-center gap-1 text-xs ${priority.color}`}
                  >
                    {priority.icon}
                    {priority.label}
                  </span>
                )}

                {/* Assignee */}
                {task.assignee && (
                  <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-[10px] font-bold text-white uppercase">
                      {task.assignee[0]}
                    </span>
                    @{task.assignee}
                  </span>
                )}

                {/* Due Date */}
                {task.dueDate && (
                  <span
                    className={`text-xs ${
                      task.dueDate.getTime() < Date.now() &&
                      !["done", "cancelled", "archived"].includes(task.status)
                        ? "text-red-400 font-medium"
                        : "text-muted-foreground"
                    }`}
                  >
                    Due {formatDate(task.dueDate)}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-secondary transition-colors cursor-pointer"
              aria-label="Close task detail"
            >
              <X className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* Linked Entities Tags */}
          {task.linkedEntities.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Linked Entities
              </p>
              <div className="flex flex-wrap gap-1.5">
                {task.linkedEntities.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-blue-900/30 text-blue-300 border border-blue-800/50"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                    {entityNames[id] ?? id.slice(0, 8)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Context Cards (SPEC-task-communication-sync P0-1) */}
          {task.linkedEntities.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Context Cards
              </p>
              <div className="space-y-2">
                {task.linkedEntities.map((id) => {
                  const ent = entitiesById[id];
                  if (!ent) return null;
                  return (
                    <div
                      key={`ctx-${id}`}
                      className="rounded-lg border border-border/60 bg-secondary/15 p-3"
                    >
                      <p className="text-sm font-medium text-foreground">
                        {ent.name}
                      </p>
                      {ent.summary && (
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                          {ent.summary}
                        </p>
                      )}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2 text-xs">
                        <div>
                          <p className="text-muted-foreground/80">What</p>
                          <p className="text-foreground">
                            {Array.isArray(ent.tags.what) ? ent.tags.what.join(", ") : ent.tags.what}
                          </p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/80">Why</p>
                          <p className="text-foreground">{ent.tags.why}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/80">How</p>
                          <p className="text-foreground">{ent.tags.how}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Cross-platform Sync Indicator (SPEC-task-communication-sync P1-1) */}
          {syncSources.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Sync Indicators
              </p>
              <div className="flex flex-wrap gap-1.5">
                {syncSources.map((item, idx) => (
                  <span
                    key={`sync-${idx}`}
                    className="inline-flex items-center text-xs px-2 py-1 rounded-md border border-emerald-800/40 bg-emerald-900/20 text-emerald-300"
                  >
                    Sync: {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Input Provenance (SPEC-task-communication-sync P0-2) */}
          {provenanceItems.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowProvenance(true)}
                className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-secondary transition-colors cursor-pointer"
              >
                來源追溯
              </button>
            </div>
          )}

          {/* Description */}
          {task.description && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Description
              </p>
              <div className="bg-secondary/20 rounded-lg p-4 border border-border/50">
                <MarkdownRenderer
                  content={task.description}
                  className="text-sm"
                />
              </div>
            </div>
          )}

          {/* Context Summary */}
          {task.contextSummary && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Context
              </p>
              <p className="text-sm text-foreground bg-secondary/20 rounded-lg p-3 border border-border/50">
                {task.contextSummary}
              </p>
            </div>
          )}

          {/* Acceptance Criteria */}
          {task.acceptanceCriteria.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Acceptance Criteria
              </p>
              <ul className="space-y-1.5">
                {task.acceptanceCriteria.map((ac, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-foreground"
                  >
                    <span className="w-5 h-5 mt-0.5 rounded border border-border flex items-center justify-center text-xs text-muted-foreground flex-shrink-0">
                      {i + 1}
                    </span>
                    {ac}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Blocked Info */}
          {task.blockedBy.length > 0 && (
            <div className="bg-red-900/10 border border-red-900/30 rounded-lg p-3">
              <p className="text-xs font-medium text-red-400 mb-1">
                Blocked By
              </p>
              <p className="text-sm text-foreground">
                {task.blockedBy.join(", ")}
              </p>
              {task.blockedReason && (
                <p className="text-sm text-red-300 mt-1">
                  {task.blockedReason}
                </p>
              )}
            </div>
          )}

          {/* Result */}
          {task.result && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                Result
              </p>
              <div className="bg-green-900/10 border border-green-900/30 rounded-lg p-4">
                <MarkdownRenderer
                  content={task.result}
                  className="text-sm"
                />
              </div>
            </div>
          )}

          {/* Rejection Reason */}
          {task.rejectionReason && (
            <div className="bg-red-900/10 border border-red-900/30 rounded-lg p-3">
              <p className="text-xs font-medium text-red-400 mb-1">
                Rejection Reason
              </p>
              <p className="text-sm text-red-300">{task.rejectionReason}</p>
            </div>
          )}

          {/* Metadata Footer */}
          <div className="border-t border-border pt-4 grid grid-cols-2 gap-3 text-xs text-muted-foreground">
            <div>
              <span className="block text-muted-foreground/70">Created by</span>
              <span className="text-foreground">{task.createdBy}</span>
            </div>
            <div>
              <span className="block text-muted-foreground/70">Project</span>
              <span className="text-foreground">
                {task.project || "unscoped"}
              </span>
            </div>
            <div>
              <span className="block text-muted-foreground/70">Created</span>
              <span className="text-foreground">
                {formatDate(task.createdAt)}
              </span>
            </div>
            <div>
              <span className="block text-muted-foreground/70">Updated</span>
              <span className="text-foreground">
                {formatDate(task.updatedAt)}
              </span>
            </div>
            {task.completedAt && (
              <div>
                <span className="block text-muted-foreground/70">
                  Completed
                </span>
                <span className="text-foreground">
                  {formatDate(task.completedAt)}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {showProvenance && provenanceItems.length > 0 && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-[60]"
            onClick={() => setShowProvenance(false)}
          />
          <div className="fixed inset-x-4 top-10 mx-auto max-w-2xl max-h-[80vh] overflow-y-auto rounded-xl border border-border bg-card p-4 z-[70]">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-foreground">來源追溯</p>
              <button
                type="button"
                onClick={() => setShowProvenance(false)}
                className="p-1 rounded hover:bg-secondary"
                aria-label="Close provenance"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-3">
              {provenanceItems.map((item, idx) => (
                <div
                  key={`prov-${idx}`}
                  className="rounded-lg border border-border/60 bg-secondary/10 p-3"
                >
                  <p className="text-xs text-muted-foreground">
                    {(item.type ?? "source").toString()}
                    {item.label ? ` • ${item.label}` : ""}
                    {item.sheet_ref ? ` • ${item.sheet_ref}` : ""}
                  </p>
                  {item.snippet && (
                    <p className="text-sm text-foreground mt-1 whitespace-pre-wrap">
                      {item.snippet}
                    </p>
                  )}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-400 underline underline-offset-2"
                    >
                      {item.url}
                    </a>
                  )}
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt={item.label ?? "provenance"}
                      className="mt-2 rounded border border-border max-h-60 object-contain"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
