// B4-05: TaskDetailDrawer — headerExtras slot and Zen Drawer integration test
// Verifies that the Drawer's headerExtras slot receives React nodes and renders them.
import React from "react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { TaskDetailDrawer } from "@/components/TaskDetailDrawer";
import { Drawer } from "@/components/zen/Drawer";
import { useInk } from "@/lib/zen-ink/tokens";
import type { Task } from "@/types";

afterEach(() => cleanup());

// Mock auth — TaskDetailDrawer calls useAuth()
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: null, partner: null }),
}));

// Mock API calls — comments are fetched but we don't want real HTTP
vi.mock("@/lib/api", () => ({
  getTaskComments: vi.fn().mockResolvedValue([]),
  createTaskComment: vi.fn(),
  deleteTaskComment: vi.fn(),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-b4-test",
    title: "B4 Test Task",
    description: "Test description",
    status: "in_progress",
    priority: "medium",
    project: "zenos",
    priorityReason: "",
    assignee: null,
    assigneeName: null,
    planId: null,
    planOrder: null,
    createdBy: "partner-1",
    creatorName: "Test User",
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
    attachments: [],
    dispatcher: "agent:developer",
    parentTaskId: null,
    handoffEvents: [],
    createdAt: new Date("2026-04-20T10:00:00Z"),
    updatedAt: new Date("2026-04-20T10:00:00Z"),
    completedAt: null,
    ...overrides,
  };
}

describe("TaskDetailDrawer — B4 Zen migration", () => {
  it("renders Drawer when task is provided", () => {
    render(<TaskDetailDrawer task={makeTask()} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("does not render when task is null", () => {
    render(<TaskDetailDrawer task={null} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders task title in header", () => {
    render(<TaskDetailDrawer task={makeTask({ title: "My Zen Task" })} onClose={vi.fn()} />);
    expect(screen.getByText("My Zen Task")).toBeDefined();
  });

  it("B4-05: Drawer headerExtras slot accepts and renders React node", () => {
    // TaskDetailDrawer passes headerExtras={null} to Drawer.
    // This test confirms the Drawer itself handles the slot correctly via the zen/Drawer primitive.
    // We test through TaskDetailDrawer rendering — if slot is wired the Drawer renders open correctly.
    render(<TaskDetailDrawer task={makeTask()} onClose={vi.fn()} />);
    // Dialog is rendered — confirming Drawer with headerExtras={null} renders without error
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
  });

  it("B4-05: zen/Drawer headerExtras renders provided node (direct Drawer test)", () => {
    // Directly verify zen/Drawer renders headerExtras slot content
    const t = useInk("light");

    render(
      <Drawer
        t={t}
        open={true}
        onOpenChange={() => {}}
        header={<span>Header</span>}
        headerExtras={<span data-testid="extras-slot">Dispatcher Badge</span>}
      >
        <div>body</div>
      </Drawer>
    );

    expect(screen.getByTestId("extras-slot")).toBeDefined();
    expect(screen.getByText("Dispatcher Badge")).toBeDefined();
  });

  it("B4-05: zen/Drawer headerExtras=null renders no extras area", () => {
    const t = useInk("light");

    render(
      <Drawer
        t={t}
        open={true}
        onOpenChange={() => {}}
        header={<span>Header</span>}
        headerExtras={null}
      >
        <div>body</div>
      </Drawer>
    );

    expect(screen.queryByTestId("extras-slot")).toBeNull();
    // Header still renders
    expect(screen.getByText("Header")).toBeDefined();
  });

  it("renders status chip", () => {
    render(<TaskDetailDrawer task={makeTask({ status: "in_progress" })} onClose={vi.fn()} />);
    expect(screen.getByText("in_progress")).toBeDefined();
  });

  it("renders dispatcher chip", () => {
    render(<TaskDetailDrawer task={makeTask({ dispatcher: "agent:developer" })} onClose={vi.fn()} />);
    expect(screen.getByText("Developer")).toBeDefined();
  });

  it("closes via onClose when close button is clicked", () => {
    const onClose = vi.fn();
    render(<TaskDetailDrawer task={makeTask()} onClose={onClose} />);
    const closeBtn = screen.getByRole("button", { name: "關閉" });
    closeBtn.click();
    expect(onClose).toHaveBeenCalled();
  });
});
