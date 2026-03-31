"use client";

import { useState, useRef, useEffect } from "react";
import type { TaskStatus, TaskPriority } from "@/types";

interface TaskFiltersProps {
  selectedStatuses: TaskStatus[];
  selectedPriority: TaskPriority | null;
  selectedProject: string | null;
  availableProjects: string[];
  onStatusChange: (statuses: TaskStatus[]) => void;
  onPriorityChange: (priority: TaskPriority | null) => void;
  onProjectChange: (project: string | null) => void;
}

const ALL_STATUSES: TaskStatus[] = [
  "todo",
  "in_progress",
  "review",
  "done",
  "cancelled",
];

const STATUS_LABELS: Record<string, string> = {
  todo: "Todo",
  in_progress: "In Progress",
  review: "Review",
  done: "Done",
  cancelled: "Cancelled",
};

const ALL_PRIORITIES: TaskPriority[] = ["critical", "high", "medium", "low"];

export function TaskFilters({
  selectedStatuses,
  selectedPriority,
  selectedProject,
  availableProjects,
  onStatusChange,
  onPriorityChange,
  onProjectChange,
}: TaskFiltersProps) {
  const [statusOpen, setStatusOpen] = useState(false);
  const statusRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (statusRef.current && !statusRef.current.contains(e.target as Node)) {
        setStatusOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function toggleStatus(status: TaskStatus) {
    if (selectedStatuses.includes(status)) {
      onStatusChange(selectedStatuses.filter((s) => s !== status));
    } else {
      onStatusChange([...selectedStatuses, status]);
    }
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Status multi-select */}
      <div className="relative" ref={statusRef}>
        <button
          onClick={() => setStatusOpen(!statusOpen)}
          className="text-sm border border-border rounded-lg px-3 py-1.5 bg-card hover:bg-secondary text-foreground cursor-pointer"
        >
          Status{selectedStatuses.length > 0 ? ` (${selectedStatuses.length})` : ""}
          <span className="ml-1 text-muted-foreground">&#9662;</span>
        </button>
        {statusOpen && (
          <div className="absolute z-10 mt-1 bg-card border border-border rounded-lg shadow-lg py-1 w-48">
            {ALL_STATUSES.map((status) => (
              <label
                key={status}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-secondary cursor-pointer text-sm text-foreground"
              >
                <input
                  type="checkbox"
                  checked={selectedStatuses.includes(status)}
                  onChange={() => toggleStatus(status)}
                  className="rounded"
                />
                {STATUS_LABELS[status]}
              </label>
            ))}
            {selectedStatuses.length > 0 && (
              <button
                onClick={() => onStatusChange([])}
                className="w-full text-left px-3 py-1.5 text-xs text-blue-400 hover:bg-secondary cursor-pointer"
              >
                Clear all
              </button>
            )}
          </div>
        )}
      </div>

      {/* Project Select */}
      <select
        value={selectedProject ?? ""}
        onChange={(e) =>
          onProjectChange(e.target.value || null)
        }
        className="text-sm border border-border rounded-lg px-3 py-1.5 bg-card text-foreground cursor-pointer"
      >
        <option value="">All Projects</option>
        {availableProjects.map((p) => (
          <option key={p} value={p}>
            {p.toUpperCase()}
          </option>
        ))}
      </select>

      {/* Priority single-select */}
      <select
        value={selectedPriority ?? ""}
        onChange={(e) =>
          onPriorityChange(e.target.value ? (e.target.value as TaskPriority) : null)
        }
        className="text-sm border border-border rounded-lg px-3 py-1.5 bg-card text-foreground cursor-pointer"
      >
        <option value="">All priorities</option>
        {ALL_PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </option>
        ))}
      </select>
    </div>
  );
}
