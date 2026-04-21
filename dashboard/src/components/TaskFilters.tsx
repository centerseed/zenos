"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { TaskStatus, TaskPriority } from "@/types";
import { Dropdown } from "@/components/zen/Dropdown";
import { Select } from "@/components/zen/Select";

interface TaskFiltersProps {
  selectedStatuses: TaskStatus[];
  selectedPriority: TaskPriority | null;
  selectedProject: string | null;
  selectedDispatcher?: string | null;
  selectedBlockedMode?: "all" | "blocked" | "unblocked";
  availableProjects: Array<{ value: string; label: string }>;
  availableDispatchers?: string[];
  onStatusChange: (statuses: TaskStatus[]) => void;
  onPriorityChange: (priority: TaskPriority | null) => void;
  onProjectChange: (project: string | null) => void;
  onDispatcherChange?: (dispatcher: string | null) => void;
  onBlockedModeChange?: (mode: "all" | "blocked" | "unblocked") => void;
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

const PRIORITY_OPTIONS = [
  { value: "", label: "All priorities" },
  ...ALL_PRIORITIES.map((p) => ({
    value: p,
    label: p.charAt(0).toUpperCase() + p.slice(1),
  })),
];

const BLOCKED_OPTIONS = [
  { value: "all", label: "All blockers" },
  { value: "blocked", label: "Blocked only" },
  { value: "unblocked", label: "Unblocked only" },
];

export function TaskFilters({
  selectedStatuses,
  selectedPriority,
  selectedProject,
  selectedDispatcher,
  selectedBlockedMode = "all",
  availableProjects,
  availableDispatchers,
  onStatusChange,
  onPriorityChange,
  onProjectChange,
  onDispatcherChange,
  onBlockedModeChange,
}: TaskFiltersProps) {
  const t = useInk("light");
  const { c, fontBody, radius } = t;

  const statusItems = ALL_STATUSES.map((s) => ({
    value: s,
    label: STATUS_LABELS[s],
  }));

  const projectOptions = [
    { value: "", label: "All Products" },
    ...availableProjects,
  ];

  const dispatcherOptions = [
    { value: "", label: "All dispatchers" },
    ...(availableDispatchers ?? []).map((d) => ({ value: d, label: d })),
  ];

  const statusLabel =
    selectedStatuses.length > 0
      ? `Status (${selectedStatuses.length})`
      : "Status";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      {/* Status multi-select */}
      <Dropdown<TaskStatus>
        t={t}
        trigger={
          <button
            type="button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              fontSize: 13,
              fontFamily: fontBody,
              fontWeight: 400,
              color: c.ink,
              background: c.surfaceHi,
              border: `1px solid ${c.inkHair}`,
              borderRadius: radius,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {statusLabel}
            <span aria-hidden="true" style={{ fontSize: 10, color: c.inkMuted }}>▾</span>
          </button>
        }
        items={statusItems}
        selected={selectedStatuses}
        multiple
        onSelect={(next) => onStatusChange(next)}
        aria-label="Status filter"
      />

      {/* Project Select */}
      <Select
        t={t}
        value={selectedProject ?? ""}
        onChange={(v) => onProjectChange(v === "" ? null : v)}
        options={projectOptions}
        aria-label="Project filter"
        style={{ width: "auto", minWidth: 130 }}
      />

      {/* Priority single-select */}
      <Select
        t={t}
        value={selectedPriority ?? ""}
        onChange={(v) => onPriorityChange(v === "" ? null : (v as TaskPriority))}
        options={PRIORITY_OPTIONS}
        aria-label="Priority filter"
        style={{ width: "auto", minWidth: 130 }}
      />

      {/* Dispatcher single-select */}
      {onDispatcherChange && (
        <Select
          t={t}
          value={selectedDispatcher ?? ""}
          onChange={(v) => onDispatcherChange(v === "" ? null : v)}
          options={dispatcherOptions}
          aria-label="Dispatcher filter"
          style={{ width: "auto", minWidth: 150 }}
        />
      )}

      {onBlockedModeChange && (
        <Select
          t={t}
          value={selectedBlockedMode}
          onChange={(v) => onBlockedModeChange((v as "all" | "blocked" | "unblocked") || "all")}
          options={BLOCKED_OPTIONS}
          aria-label="Blocked filter"
          style={{ width: "auto", minWidth: 150 }}
        />
      )}
    </div>
  );
}
