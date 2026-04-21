import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectRecapRail } from "@/features/projects/ProjectRecapRail";
import type { ProjectProgressResponse } from "@/lib/api";

vi.mock("@/components/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    partner: {
      activeWorkspaceId: "ws-active",
      homeWorkspaceId: "ws-home",
    },
  }),
}));

vi.mock("@/lib/copilot/useCopilotChat", () => ({
  useCopilotChat: () => ({
    status: "idle",
    connectorStatus: "connected",
    messages: [
      { role: "system", content: "事件：rate_limit_event", timestamp: 1 },
      { role: "user", content: "請整理一下", timestamp: 2 },
      { role: "assistant", content: "這是整理後的 recap", timestamp: 3 },
    ],
    streamingText: "",
    capability: null,
    lastError: null,
    send: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
  }),
}));

function makeProgress(): ProjectProgressResponse {
  return {
    project: {
      id: "project-1",
      name: "ZenOS",
      type: "product",
      summary: "summary",
      tags: { what: [], why: "", how: "", who: [] },
      status: "active",
      parentId: null,
      details: null,
      confirmedByUser: true,
      owner: "Owner",
      sources: [],
      visibility: "public",
      lastReviewedAt: null,
      createdAt: new Date("2026-04-18T00:00:00Z"),
      updatedAt: new Date("2026-04-21T12:00:00Z"),
    },
    active_plans: [],
    open_work_groups: [],
    milestones: [],
    recent_progress: [],
  };
}

describe("ProjectRecapRail", () => {
  it("hides internal system event messages from the visible chat log", () => {
    render(
      <ProjectRecapRail
        open
        onOpenChange={() => {}}
        progress={makeProgress()}
        preset="claude_code"
        nextStep="Review current progress"
        onRecapChange={() => {}}
      />
    );

    expect(screen.queryByText("事件：rate_limit_event")).not.toBeInTheDocument();
    expect(screen.getByText("請整理一下")).toBeInTheDocument();
    expect(screen.getByText("這是整理後的 recap")).toBeInTheDocument();
  });

  it("emits assistant updates so the product page can refresh after helper writes", () => {
    const onAssistantUpdate = vi.fn();

    render(
      <ProjectRecapRail
        open
        onOpenChange={() => {}}
        progress={makeProgress()}
        preset="claude_code"
        nextStep="Review current progress"
        onRecapChange={() => {}}
        onAssistantUpdate={onAssistantUpdate}
      />
    );

    expect(onAssistantUpdate).toHaveBeenCalledWith("這是整理後的 recap");
  });

  it("reveals the raw Claude Code transcript on demand", () => {
    render(
      <ProjectRecapRail
        open
        onOpenChange={() => {}}
        progress={makeProgress()}
        preset="claude_code"
        nextStep="Review current progress"
        onRecapChange={() => {}}
      />
    );

    expect(screen.queryByTestId("project-raw-transcript")).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByTestId("project-raw-transcript-toggle")[0]!);

    expect(screen.getByTestId("project-raw-transcript")).toHaveTextContent("[system] 事件：rate_limit_event");
    expect(screen.getByTestId("project-raw-transcript")).toHaveTextContent("[assistant] 這是整理後的 recap");
  });
});
