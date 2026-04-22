import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectRecapRail } from "@/features/projects/ProjectRecapRail";
import type { ProjectProgressResponse } from "@/lib/api";

const chatState = vi.hoisted(() => ({
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
}));

vi.mock("@/components/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/components/zen/Toast", () => ({
  useToast: () => ({
    pushToast: vi.fn(),
  }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    partner: {
      apiKey: "pk-test", // pragma: allowlist secret
      activeWorkspaceId: "ws-active",
      homeWorkspaceId: "ws-home",
    },
  }),
}));

vi.mock("@/lib/agent-config", () => ({
  buildHelperInstallAndStartCommand: () => "helper-start-command",
  canCopyAgentConfig: () => true,
}));

vi.mock("@/lib/cowork-helper", () => ({
  checkCoworkHelperHealth: vi.fn().mockResolvedValue({
    ok: true,
    status: "ok",
    workspaceProbe: {
      ok: true,
      workspaceId: "ws-active",
      workspaceName: "Active Workspace",
    },
  }),
  getDefaultHelperBaseUrl: () => "http://127.0.0.1:4317",
  getDefaultHelperToken: () => "helper-token",
  getDefaultHelperCwd: () => "/tmp/helper",
  getDefaultHelperModel: () => "sonnet",
  setDefaultHelperBaseUrl: vi.fn(),
  setDefaultHelperToken: vi.fn(),
  setDefaultHelperCwd: vi.fn(),
  setDefaultHelperModel: vi.fn(),
}));

vi.mock("@/lib/copilot/useCopilotChat", () => ({
  useCopilotChat: () => ({
    status: chatState.status,
    connectorStatus: chatState.connectorStatus,
    messages: chatState.messages,
    streamingText: chatState.streamingText,
    capability: chatState.capability,
    lastError: chatState.lastError,
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
  beforeEach(() => {
    chatState.status = "idle";
    chatState.connectorStatus = "connected";
    chatState.messages = [
      { role: "system", content: "事件：rate_limit_event", timestamp: 1 },
      { role: "user", content: "請整理一下", timestamp: 2 },
      { role: "assistant", content: "這是整理後的 recap", timestamp: 3 },
    ];
    chatState.streamingText = "";
    chatState.capability = null;
    chatState.lastError = null;
  });

  it("shows only a compact helper status in the normal rail state", () => {
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

    expect(screen.getByText("Helper 已連線")).toBeInTheDocument();
    expect(screen.queryByText("Claude Code 原文")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "設定 helper" })).not.toBeInTheDocument();
  });

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
    expect(screen.getAllByText("請整理一下").length).toBeGreaterThan(0);
    expect(screen.getAllByText("這是整理後的 recap").length).toBeGreaterThan(0);
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

  it("does not re-emit the same assistant recap across identical rerenders", () => {
    const onAssistantUpdate = vi.fn();

    const { rerender } = render(
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

    rerender(
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

    expect(onAssistantUpdate).toHaveBeenCalledTimes(1);
  });

  it("opens helper setup dialog in-place when helper is unavailable", () => {
    chatState.connectorStatus = "disconnected";

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

    fireEvent.click(screen.getByRole("button", { name: "設定 helper" }));
    expect(screen.getAllByRole("dialog").length).toBeGreaterThan(1);
    expect(screen.getByRole("heading", { name: "設定 helper" })).toBeInTheDocument();
    expect(screen.getByLabelText("Helper Base URL")).toBeInTheDocument();

    chatState.connectorStatus = "connected";
  });
});
