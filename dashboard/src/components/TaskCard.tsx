"use client";

import { useState } from "react";
import type { Task } from "@/types";

interface TaskCardProps {
  task: Task;
}

const priorityColors: Record<string, string> = {
  critical: "bg-red-900/50 text-red-400",
  high: "bg-orange-900/50 text-orange-400",
  medium: "bg-blue-900/50 text-blue-400",
  low: "bg-[#1F1F23] text-[#71717A]",
};

function formatDate(date: Date | null): string | null {
  if (!date) return null;
  return date.toLocaleDateString("zh-TW");
}

function isOverdue(date: Date | null): boolean {
  if (!date) return false;
  return date.getTime() < Date.now();
}

export function TaskCard({ task }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false);

  const dueDateStr = formatDate(task.dueDate);
  const overdue = task.status !== "done" && task.status !== "cancelled" && isOverdue(task.dueDate);

  return (
    <div
      className="border border-[#1F1F23] rounded-lg p-4 bg-[#111113] hover:border-[#2A2A2E] transition-colors cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="text-sm font-medium text-white leading-tight">
          {task.title}
        </h4>
        <span
          className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${priorityColors[task.priority] ?? "bg-[#1F1F23] text-[#71717A]"}`}
        >
          {task.priority}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-[#71717A]">
        {task.assignee && <span>@{task.assignee}</span>}
        {dueDateStr && (
          <span className={overdue ? "text-red-400 font-medium" : ""}>
            Due {dueDateStr}
          </span>
        )}
        {task.linkedEntities.length > 0 && (
          <span>{task.linkedEntities.length} linked</span>
        )}
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-[#1F1F23] space-y-3 text-sm">
          {task.description && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Description</p>
              <p className="text-[#FAFAFA]">{task.description}</p>
            </div>
          )}

          {task.contextSummary && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Context</p>
              <p className="text-[#FAFAFA]">{task.contextSummary}</p>
            </div>
          )}

          {task.acceptanceCriteria.length > 0 && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Acceptance Criteria</p>
              <ul className="list-disc list-inside text-[#FAFAFA] space-y-0.5">
                {task.acceptanceCriteria.map((ac, i) => (
                  <li key={i}>{ac}</li>
                ))}
              </ul>
            </div>
          )}

          {task.blockedBy.length > 0 && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Blocked By</p>
              <p className="text-[#FAFAFA]">{task.blockedBy.join(", ")}</p>
            </div>
          )}

          {task.blockedReason && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Blocked Reason</p>
              <p className="text-[#FAFAFA]">{task.blockedReason}</p>
            </div>
          )}

          {task.result && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Result</p>
              <p className="text-[#FAFAFA]">{task.result}</p>
            </div>
          )}

          {task.rejectionReason && (
            <div>
              <p className="text-xs font-medium text-[#71717A] mb-1">Rejection Reason</p>
              <p className="text-red-400">{task.rejectionReason}</p>
            </div>
          )}

          <div className="flex gap-4 text-xs text-[#71717A] pt-1">
            <span>Created by {task.createdBy}</span>
            <span>Updated {formatDate(task.updatedAt)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
