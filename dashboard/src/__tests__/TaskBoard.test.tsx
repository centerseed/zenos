import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { TaskBoard } from "@/components/TaskBoard";
import type { Task } from "@/types";

const dndHandlers: {
  onDragStart?: (event: unknown) => void;
  onDragEnd?: (event: unknown) => void;
} = {};

vi.mock("@/components/TaskDetailDrawer", () => ({
  TaskDetailDrawer: ({ task }: { task: Task | null }) =>
    task ? <div data-testid="task-drawer">{task.title}</div> : null,
}));

vi.mock("@dnd-kit/core", () => ({
  DndContext: ({
    children,
    onDragStart,
    onDragEnd,
  }: {
    children: React.ReactNode;
    onDragStart?: (event: unknown) => void;
    onDragEnd?: (event: unknown) => void;
  }) => {
    dndHandlers.onDragStart = onDragStart;
    dndHandlers.onDragEnd = onDragEnd;
    return <div>{children}</div>;
  },
  DragOverlay: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PointerSensor: function PointerSensor() {
    return null;
  },
  useSensor: () => ({}),
  useSensors: (...sensors: unknown[]) => sensors,
  useDroppable: () => ({
    setNodeRef: () => {},
    isOver: false,
  }),
  useDraggable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: () => {},
    isDragging: false,
  }),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    title: "委託稅理士",
    description: "task desc",
    status: "in_progress",
    priority: "high",
    project: "zenos",
    priorityReason: "",
    assignee: null,
    assigneeName: null,
    planId: null,
    planOrder: null,
    productId: "product-1",
    createdBy: "partner-1",
    creatorName: "Owner",
    linkedEntities: [],
    linkedProtocol: null,
    linkedBlindspot: null,
    sourceType: "manual",
    contextSummary: "",
    dueDate: null,
    blockedBy: [],
    blockedReason: null,
    acceptanceCriteria: [],
    confirmedByCreator: false,
    rejectionReason: null,
    result: "done result",
    completedBy: null,
    attachments: [],
    dispatcher: "human",
    parentTaskId: null,
    handoffEvents: [],
    createdAt: new Date("2026-04-22T00:00:00Z"),
    updatedAt: new Date("2026-04-22T00:00:00Z"),
    completedAt: null,
    ...overrides,
  };
}

describe("TaskBoard drag selection guard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("does not open drawer when clicking immediately after a drag-end status change", () => {
    const onStatusChange = vi.fn().mockResolvedValue(undefined);

    render(<TaskBoard tasks={[makeTask()]} onStatusChange={onStatusChange} />);

    act(() => {
      dndHandlers.onDragEnd?.({
        active: { id: "task-1" },
        over: { id: "done" },
      });
    });

    fireEvent.click(screen.getByText("委託稅理士"));

    expect(onStatusChange).toHaveBeenCalledWith("task-1", "done");
    expect(screen.queryByTestId("task-drawer")).toBeNull();

    act(() => {
      vi.advanceTimersByTime(500);
    });

    fireEvent.click(screen.getByText("委託稅理士"));

    expect(screen.getByTestId("task-drawer")).toHaveTextContent("委託稅理士");
  });

  it("asks for result when dragging into review instead of opening the drawer", async () => {
    const onStatusChange = vi.fn().mockResolvedValue(undefined);
    const onUpdateTask = vi.fn().mockResolvedValue(undefined);

    render(
      <TaskBoard
        tasks={[makeTask({ result: "" })]}
        onStatusChange={onStatusChange}
        onUpdateTask={onUpdateTask}
      />
    );

    act(() => {
      dndHandlers.onDragEnd?.({
        active: { id: "task-1" },
        over: { id: "review" },
      });
    });

    expect(screen.queryByTestId("task-drawer")).toBeNull();
    expect(screen.getByText("送審前補上成果")).toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText(
        "例如：已取得完整公司文件包，並整理缺件清單供下一步審查。"
      ),
      { target: { value: "已補齊審查摘要" } }
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "送審" }));
    });

    expect(onUpdateTask).toHaveBeenCalledWith("task-1", {
      result: "已補齊審查摘要",
      status: "review",
    });
    expect(onStatusChange).not.toHaveBeenCalled();
    expect(screen.queryByText("送審前補上成果")).toBeNull();
  });
});
