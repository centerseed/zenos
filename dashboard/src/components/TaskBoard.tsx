"use client";

import type { Task, TaskStatus } from "@/types";
import { TaskCard } from "./TaskCard";

interface TaskBoardProps {
  tasks: Task[];
}

const COLUMN_ORDER: TaskStatus[] = ["todo", "in_progress", "review", "blocked", "backlog"];

const COLUMN_LABELS: Record<string, string> = {
  todo: "TODO",
  in_progress: "IN PROGRESS",
  review: "REVIEW",
  blocked: "BLOCKED",
  backlog: "BACKLOG",
};

const COLUMN_HEADER_COLORS: Record<string, string> = {
  todo: "bg-blue-900/50 text-blue-400",
  in_progress: "bg-yellow-900/50 text-yellow-400",
  review: "bg-purple-900/50 text-purple-400",
  blocked: "bg-red-900/50 text-red-400",
  backlog: "bg-[#1F1F23] text-[#71717A]",
};

export function TaskBoard({ tasks }: TaskBoardProps) {
  const grouped: Record<string, Task[]> = {};
  for (const col of COLUMN_ORDER) {
    grouped[col] = [];
  }
  for (const task of tasks) {
    if (grouped[task.status]) {
      grouped[task.status].push(task);
    }
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {COLUMN_ORDER.map((status) => {
        const columnTasks = grouped[status];
        return (
          <div key={status} className="flex-shrink-0 w-72">
            <div
              className={`rounded-t-lg px-3 py-2 flex items-center justify-between ${COLUMN_HEADER_COLORS[status] ?? "bg-[#1F1F23] text-[#71717A]"}`}
            >
              <span className="text-xs font-semibold uppercase">
                {COLUMN_LABELS[status] ?? status}
              </span>
              <span className="text-xs font-medium rounded-full bg-white/10 px-2 py-0.5">
                {columnTasks.length}
              </span>
            </div>
            <div className="bg-[#0A0A0B] rounded-b-lg p-2 space-y-2 min-h-[120px] border-x border-b border-[#1F1F23]">
              {columnTasks.length === 0 ? (
                <p className="text-xs text-[#71717A] text-center py-6">No tasks</p>
              ) : (
                columnTasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
