import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { MorningReport } from "@/components/MorningReport";
import type { Task } from "@/types";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    title: "Default task",
    description: "",
    status: "todo",
    priority: "medium",
    project: "zenos",
    priorityReason: "",
    assignee: null,
    createdBy: "partner-1",
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
    sourceMetadata: {},
    ...overrides,
  };
}

describe("MorningReport", () => {
  it("shows empty state when there are no personal risks", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-04T00:00:00Z"));

    render(<MorningReport tasks={[makeTask()]} partnerId="partner-1" onSelectTask={() => {}} />);

    expect(screen.getByText("今日無待處理風險")).toBeInTheDocument();
  });

  it("groups personal risk tasks into three buckets and selects a task on click", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-04T00:00:00Z"));
    const onSelectTask = vi.fn();

    render(
      <MorningReport
        partnerId="partner-1"
        onSelectTask={onSelectTask}
        tasks={[
          makeTask({
            id: "upcoming",
            title: "Upcoming task",
            assignee: "partner-1",
            dueDate: new Date("2026-04-06T00:00:00Z"),
            createdBy: "someone-else",
          }),
          makeTask({
            id: "overdue",
            title: "Overdue task",
            assignee: "partner-1",
            dueDate: new Date("2026-04-03T00:00:00Z"),
            createdBy: "someone-else",
          }),
          makeTask({
            id: "idle",
            title: "Idle task",
            assignee: "partner-9",
            createdBy: "partner-1",
            updatedAt: new Date("2026-04-01T00:00:00Z"),
          }),
        ]}
      />
    );

    expect(screen.getByText("Upcoming task")).toBeInTheDocument();
    expect(screen.getByText("Overdue task")).toBeInTheDocument();
    expect(screen.getByText("Idle task")).toBeInTheDocument();
    expect(screen.getByText("2 天後到期")).toBeInTheDocument();
    expect(screen.getByText("逾期 1 天")).toBeInTheDocument();
    expect(screen.getByText("未開始 72h")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Overdue task/i }));
    expect(onSelectTask).toHaveBeenCalledWith(expect.objectContaining({ id: "overdue" }));
  });
});
