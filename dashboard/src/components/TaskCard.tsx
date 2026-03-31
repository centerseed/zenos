"use client";

import type { Task } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { extractFirstImage } from "./MarkdownRenderer";
import {
  AlertTriangle,
  ArrowUp,
  Minus,
  ArrowDown,
} from "lucide-react";

interface TaskCardProps {
  task: Task;
  onSelect?: (task: Task) => void;
  entityNames?: Record<string, string>;
}

const priorityIcons: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="w-3.5 h-3.5 text-red-400" />,
  high: <ArrowUp className="w-3.5 h-3.5 text-orange-400" />,
  medium: <Minus className="w-3.5 h-3.5 text-blue-400" />,
  low: <ArrowDown className="w-3.5 h-3.5 text-muted-foreground" />,
};

const priorityBg: Record<string, string> = {
  critical: "bg-red-900/40",
  high: "bg-orange-900/40",
  medium: "bg-blue-900/40",
  low: "bg-secondary",
};

function formatDate(date: Date | null): string | null {
  if (!date) return null;
  return date.toLocaleDateString("zh-TW", { month: "short", day: "numeric" });
}

function isOverdue(task: Task): boolean {
  if (!task.dueDate) return false;
  if (["done", "cancelled", "archived"].includes(task.status)) return false;
  return task.dueDate.getTime() < Date.now();
}

export function TaskCard({ task, onSelect, entityNames = {} }: TaskCardProps) {
  const thumbnail = task.description ? extractFirstImage(task.description) : null;
  const overdue = isOverdue(task);
  const dueDateStr = formatDate(task.dueDate);

  // Extract first ~80 chars of description for preview (strip markdown)
  const descPreview = task.description
    ? task.description
        .replace(/!\[.*?\]\(.*?\)/g, "") // remove images
        .replace(/\[([^\]]+)\]\(.*?\)/g, "$1") // simplify links
        .replace(/[#*_~`>|]/g, "") // remove markdown chars
        .replace(/\n+/g, " ")
        .trim()
        .slice(0, 100)
    : null;

  return (
    <Card
      className={`ring-1 ring-border/80 hover:ring-blue-500/50 transition-all duration-200 cursor-pointer group ${
        overdue ? "ring-red-500/30" : ""
      }`}
      onClick={() => onSelect?.(task)}
      role="button"
      tabIndex={0}
      aria-label={`Open task: ${task.title}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect?.(task);
        }
      }}
    >
      {/* Cover/Thumbnail Image */}
      {thumbnail && (
        <div className="relative w-full h-32 overflow-hidden rounded-t-lg">
          <img
            src={thumbnail}
            alt="Task attachment"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-card/80 to-transparent" />
        </div>
      )}

      <CardHeader className="pb-2 pt-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium text-foreground leading-tight group-hover:text-blue-300 transition-colors line-clamp-2">
            {task.title}
          </CardTitle>

          {/* Priority Icon */}
          <span
            className={`flex-shrink-0 p-1 rounded ${priorityBg[task.priority] ?? "bg-secondary"}`}
            title={task.priority}
          >
            {priorityIcons[task.priority] ?? (
              <Minus className="w-3.5 h-3.5 text-muted-foreground" />
            )}
          </span>
        </div>

        {/* Description Preview */}
        {descPreview && (
          <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed">
            {descPreview}
          </p>
        )}
      </CardHeader>

      <CardContent className="pt-0 pb-3 space-y-2.5">
        {/* Linked Entities Tags */}
        {task.linkedEntities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {task.linkedEntities.slice(0, 3).map((id) => (
              <span
                key={id}
                className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-blue-900/25 text-blue-300 border border-blue-800/40"
              >
                <span className="w-1 h-1 rounded-full bg-blue-400" />
                {entityNames[id] ?? id.slice(0, 6)}
              </span>
            ))}
            {task.linkedEntities.length > 3 && (
              <span className="text-[10px] px-1.5 py-0.5 text-muted-foreground">
                +{task.linkedEntities.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Footer Row: Assignee, Due Date, Project */}
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <div className="flex items-center gap-2">
            {/* Assignee Avatar & Name */}
            {(task.assignee || task.assigneeName) && (
              <span
                className="inline-flex items-center gap-1"
                title={`Assignee: ${task.assigneeName || task.assignee}`}
              >
                <span className="w-4 h-4 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-[8px] font-bold text-white uppercase">
                  {(task.assigneeName || task.assignee || "?")[0]}
                </span>
                <span className="truncate max-w-[60px]">{task.assigneeName || "Unknown"}</span>
              </span>
            )}

            {/* Creator Name (Small) */}
            {task.creatorName && (
              <span className="text-muted-foreground/60 border-l border-border pl-2">
                by {task.creatorName}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Due Date */}
            {dueDateStr && (
              <span
                className={`${overdue ? "text-red-400 font-medium" : ""}`}
              >
                {dueDateStr}
              </span>
            )}
            
            {/* Project label */}
            {task.project && (
              <span className="px-1 py-0.5 rounded bg-secondary text-muted-foreground truncate max-w-[60px]">
                {task.project}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
