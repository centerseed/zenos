import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { TaskCard } from "@/components/TaskCard";
import type { Task } from "@/types";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    title: "Follow up spec",
    description: "",
    status: "todo",
    priority: "medium",
    project: "zenos",
    priorityReason: "",
    assignee: "partner-1",
    createdBy: "partner-2",
    linkedEntities: [],
    linkedProtocol: null,
    linkedBlindspot: null,
    sourceType: "chat",
    contextSummary: "",
    dueDate: null,
    blockedBy: [],
    blockedReason: null,
    acceptanceCriteria: [],
    confirmedByCreator: false,
    rejectionReason: null,
    result: null,
    completedBy: null,
    createdAt: new Date("2026-04-01T00:00:00Z"),
    updatedAt: new Date("2026-04-01T00:00:00Z"),
    completedAt: null,
    ...overrides,
  };
}

describe("TaskCard risk badges", () => {
  it("renders overdue badge text", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-03T00:00:00Z"));

    render(
      <TaskCard
        task={makeTask({
          dueDate: new Date("2026-04-02T00:00:00Z"),
        })}
      />
    );

    expect(screen.getByText("逾期 1 天")).toBeInTheDocument();
  });

  it("renders upcoming due badge text", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-01T00:00:00Z"));

    render(
      <TaskCard
        task={makeTask({
          status: "in_progress",
          dueDate: new Date("2026-04-03T00:00:00Z"),
        })}
      />
    );

    expect(screen.getByText("2 天後到期")).toBeInTheDocument();
  });

  it("renders idle todo badge text", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-04T00:00:00Z"));

    render(
      <TaskCard
        task={makeTask({
          updatedAt: new Date("2026-04-01T00:00:00Z"),
        })}
      />
    );

    expect(screen.getByText("未開始 72h")).toBeInTheDocument();
  });

  it("does not render risk badges for done task", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-04T00:00:00Z"));

    render(
      <TaskCard
        task={makeTask({
          status: "done",
          dueDate: new Date("2026-04-02T00:00:00Z"),
          updatedAt: new Date("2026-04-01T00:00:00Z"),
        })}
      />
    );

    expect(screen.queryByText(/逾期/)).not.toBeInTheDocument();
    expect(screen.queryByText(/天後到期/)).not.toBeInTheDocument();
    expect(screen.queryByText(/未開始/)).not.toBeInTheDocument();
  });
});
