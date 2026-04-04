"use client";

import type { Task } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { extractFirstImage } from "./MarkdownRenderer";
import { getOverdueDays, getTaskRiskBadges } from "@/lib/task-risk";
import {
  AlertTriangle,
  ArrowUp,
  Minus,
  ArrowDown,
  Layers,
  Calendar,
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
  critical: "bg-red-500/20 border-red-500/30",
  high: "bg-orange-500/20 border-orange-500/30",
  medium: "bg-yellow-500/20 border-yellow-500/30",
  low: "bg-blue-500/20 border-blue-500/30",
};

function formatDate(date: Date | null): string {
  if (!date) return "";
  return date.toLocaleDateString("zh-TW", {
    month: "short",
    day: "numeric",
  });
}

export function TaskCard({ task, onSelect, entityNames = {} }: TaskCardProps) {
  const thumbnail = task.description ? extractFirstImage(task.description) : null;
  const overdue = getOverdueDays(task) !== null;
  const dueDateStr = formatDate(task.dueDate);
  const riskBadges = getTaskRiskBadges(task);
  
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
      className={`relative overflow-hidden transition-all duration-300 cursor-pointer group border-white/10 hover:border-blue-500/50 hover:shadow-[0_8px_30px_rgb(0,0,0,0.6)] hover:-translate-y-0.5 active:scale-[0.985] ${
        overdue ? "bg-red-950/10" : "bg-[#141414]"
      }`}
      onClick={() => onSelect?.(task)}
    >
      {/* Selection Glow */}
      <div className="absolute inset-0 bg-blue-500/[0.03] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

      {thumbnail && (
        <div className="relative w-full h-28 overflow-hidden border-b border-white/5">
          <img
            src={thumbnail}
            alt=""
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110 opacity-80 group-hover:opacity-100"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
        </div>
      )}

      <CardHeader className="pb-2 pt-3 px-3.5">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-[13px] font-bold text-white leading-snug group-hover:text-blue-300 transition-colors line-clamp-2">
            {task.title}
          </CardTitle>

          <span
            className={`flex-shrink-0 p-1 rounded-md border ${priorityBg[task.priority] ?? "bg-secondary"}`}
          >
            {priorityIcons[task.priority]}
          </span>
        </div>

        {descPreview && (
          <p className="text-[11px] text-gray-300 mt-1.5 line-clamp-2 leading-relaxed font-normal opacity-90">
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
                className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/20 font-bold tracking-tight"
              >
                {entityNames[id] ?? id.slice(0, 6)}
              </span>
            ))}
          </div>
        )}

        {riskBadges.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {riskBadges.map((badge) => (
              <span
                key={badge.kind}
                className={`rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-tight ${badge.className}`}
              >
                {badge.label}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-[10px] border-t border-white/5 pt-2.5">
          <div className="flex items-center gap-2">
            <div className="relative">
              <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-[9px] font-black text-white shadow-md ring-1 ring-white/20">
                {(displayName || "?")[0].toUpperCase()}
              </div>
              {isAgentCreated && (
                <div className="absolute -bottom-1 -right-1 bg-black rounded-full p-0.5 ring-1 ring-white/20 shadow-xs">
                  <Bot className="w-2.5 h-2.5 text-blue-400" />
                </div>
              )}
            </div>
            <span className="truncate max-w-[80px] font-bold text-gray-200 group-hover:text-white">
              {displayName}
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            {dueDateStr && (
              <div className={`flex items-center gap-1 font-bold ${overdue ? "text-red-400" : "text-gray-400"}`}>
                <Calendar className="w-2.5 h-2.5" />
                <span>{dueDateStr}</span>
              </div>
            )}
            
            {task.project && (
              <span className="px-1.5 py-0.5 rounded-[4px] bg-white/10 text-[9px] font-black uppercase tracking-widest text-gray-400 border border-white/10">
                {task.project}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
