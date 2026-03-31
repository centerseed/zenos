"use client";

import type { Task } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { extractFirstImage } from "./MarkdownRenderer";
import {
  AlertTriangle,
  ArrowUp,
  Minus,
  ArrowDown,
  Layers,
  Calendar,
  User,
  Bot,
} from "lucide-react";

interface TaskCardProps {
  task: Task;
  onSelect?: (task: Task) => void;
  entityNames?: Record<string, string>;
}

const priorityIcons: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="w-3.5 h-3.5 text-red-400" />,
  high: <ArrowUp className="w-3.5 h-3.5 text-orange-400" />,
  medium: <Minus className="w-3.5 h-3.5 text-yellow-400" />,
  low: <ArrowDown className="w-3.5 h-3.5 text-blue-400" />,
};

const priorityBg: Record<string, string> = {
  critical: "bg-red-500/15 border-red-500/20",
  high: "bg-orange-500/15 border-orange-500/20",
  medium: "bg-yellow-500/15 border-yellow-500/20",
  low: "bg-blue-500/15 border-blue-500/20",
};

function formatDate(date: Date | null): string {
  if (!date) return "";
  return date.toLocaleDateString("zh-TW", {
    month: "short",
    day: "numeric",
  });
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
  
  // Clean logic for the card avatar and name
  const isAgentCreated = task.creatorName?.includes("agent") || task.createdBy?.includes("agent");
  const mainName = task.assigneeName || task.assignee || task.creatorName || task.createdBy || "Unassigned";
  const displayName = mainName.replace(/^agent \(by (.*?)\)$/, "$1");

  const descPreview = task.description
    ? task.description
        .replace(/!\[.*?\]\(.*?\)/g, "")
        .replace(/\[([^\]]+)\]\(.*?\)/g, "$1")
        .replace(/[#*_~`>|]/g, "")
        .replace(/\n+/g, " ")
        .trim()
        .slice(0, 100)
    : null;

  return (
    <Card
      className={`relative overflow-hidden transition-all duration-300 cursor-pointer group border-border/40 hover:border-blue-500/40 hover:shadow-[0_8px_30px_rgb(0,0,0,0.5)] hover:-translate-y-0.5 ${
        overdue ? "bg-red-950/5" : "bg-gradient-to-b from-card to-card/95"
      }`}
      onClick={() => onSelect?.(task)}
    >
      {/* Selection Glow */}
      <div className="absolute inset-0 bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

      {thumbnail && (
        <div className="relative w-full h-28 overflow-hidden border-b border-border/20">
          <img
            src={thumbnail}
            alt=""
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
        </div>
      )}

      <CardHeader className="pb-2 pt-3 px-3.5">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-[13px] font-semibold text-foreground/90 leading-snug group-hover:text-blue-300 transition-colors line-clamp-2">
            {task.title}
          </CardTitle>

          <span
            className={`flex-shrink-0 p-1 rounded-md border ${priorityBg[task.priority] ?? "bg-secondary"}`}
          >
            {priorityIcons[task.priority]}
          </span>
        </div>

        {descPreview && (
          <p className="text-[11px] text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed opacity-70 font-light">
            {descPreview}
          </p>
        )}
      </CardHeader>

      <CardContent className="pt-0 pb-3 px-3.5 space-y-3">
        {/* Tags */}
        {task.linkedEntities.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {task.linkedEntities.slice(0, 2).map((id) => (
              <span
                key={id}
                className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/10 font-medium tracking-tight"
              >
                {entityNames[id] ?? id.slice(0, 6)}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-[10px] border-t border-border/30 pt-2.5">
          <div className="flex items-center gap-2">
            <div className="relative">
              <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-indigo-600 to-purple-500 flex items-center justify-center text-[9px] font-bold text-white shadow-sm ring-1 ring-white/10">
                {(displayName || "?")[0].toUpperCase()}
              </div>
              {isAgentCreated && (
                <div className="absolute -bottom-1 -right-1 bg-background rounded-full p-0.5 ring-1 ring-border shadow-xs">
                  <Bot className="w-2 h-2 text-blue-400" />
                </div>
              )}
            </div>
            <span className="truncate max-w-[80px] font-medium text-foreground/80 group-hover:text-foreground">
              {displayName}
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            {dueDateStr && (
              <div className={`flex items-center gap-1 ${overdue ? "text-red-400 font-bold" : "text-muted-foreground/60"}`}>
                <Calendar className="w-2.5 h-2.5" />
                <span>{dueDateStr}</span>
              </div>
            )}
            
            {task.project && (
              <span className="px-1.5 py-0.5 rounded-[4px] bg-white/5 text-[9px] font-black uppercase tracking-widest text-muted-foreground/50 border border-white/5">
                {task.project}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
