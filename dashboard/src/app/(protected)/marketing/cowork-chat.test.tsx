import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockCheckCoworkHelperHealth = vi.fn();
const mockStreamCoworkChat = vi.fn();
const mockCancelCoworkRequest = vi.fn();
const mockFetchGraphContext = vi.fn();

vi.mock("@/lib/cowork-helper", () => ({
  cancelCoworkRequest: (...args: unknown[]) => mockCancelCoworkRequest(...args),
  checkCoworkHelperHealth: (...args: unknown[]) => mockCheckCoworkHelperHealth(...args),
  streamCoworkChat: (...args: unknown[]) => mockStreamCoworkChat(...args),
  getDefaultHelperBaseUrl: () => "http://127.0.0.1:4317",
  getDefaultHelperToken: () => "",
  getDefaultHelperCwd: () => "/tmp/workspace",
  getDefaultHelperModel: () => "sonnet",
  setDefaultHelperBaseUrl: vi.fn(),
  setDefaultHelperToken: vi.fn(),
  setDefaultHelperCwd: vi.fn(),
  setDefaultHelperModel: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    partner: { id: "partner-1" },
    user: {
      getIdToken: vi.fn(async () => "test-token"),
    },
  }),
}));

vi.mock("@/lib/graph-context", () => ({
  fetchGraphContext: (...args: unknown[]) => mockFetchGraphContext(...args),
}));

import { CoworkChatSheet } from "@/app/(protected)/marketing/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  mockCheckCoworkHelperHealth.mockResolvedValue({
    ok: true,
    status: "ok",
    message: undefined,
    capability: null,
  });
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    },
    configurable: true,
  });
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText: vi.fn(async () => {}) },
    configurable: true,
  });
  mockFetchGraphContext.mockResolvedValue({
    seed: {
      id: "proj-1",
      name: "Paceriz",
      type: "product",
      level: 1,
      status: "active",
      summary: "跑步產品",
      tags: { what: ["跑步"], why: "建立習慣", how: "", who: ["新手"] },
    },
    fallback_mode: "normal",
    neighbors: [],
    partial: false,
    errors: [],
    truncated: false,
    truncation_details: { dropped_l2: 0, dropped_l3: 0, summary_truncated: 0 },
    estimated_tokens: 12,
    cached_at: new Date("2026-04-15T00:00:00Z"),
  });
});

function renderSheet(overrides?: Record<string, unknown>) {
  const onApply = vi.fn(async () => {});
  const utils = render(
    <CoworkChatSheet
      campaignId="proj-1"
      onError={vi.fn()}
      fieldContext={{
        fieldId: "strategy",
        fieldLabel: "策略設定",
        currentPhase: "strategy",
        suggestedSkill: "/marketing-plan",
        projectSummary: "官網 Blog / 長期經營",
        fieldValue: { audience: ["跑步新手"], tone: "直接" },
        relatedContext: "上輪摘要",
        conflictVersion: "v1",
        onApply,
        ...overrides,
      }}
    />
  );
  fireEvent.click(screen.getByText("AI 討論（Beta）"));
  return { ...utils, onApply };
}

describe("CoworkChatSheet", () => {
  it("shows loaded context for field discussion", async () => {
    renderSheet();
    expect(screen.getAllByText("討論這段：策略設定").length).toBeGreaterThan(0);
    expect(screen.getByText("策略設定 / 已載入範圍")).toBeInTheDocument();
    expect(screen.getByText("查看 prompt / context")).toBeInTheDocument();
  });

  it("opens as a drawer dialog on mobile-sized interaction entry", async () => {
    renderSheet();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows repair guidance when helper is unavailable", async () => {
    mockCheckCoworkHelperHealth.mockResolvedValue({
      ok: false,
      status: "offline",
      message: "helper unavailable",
      capability: null,
    });
    renderSheet();
    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 未連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Connector 未連線" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "收起引導" })).toBeInTheDocument();
      expect(screen.getByText("複製啟動指令")).toBeInTheDocument();
    });
  });

  it("shows missing skills warning from capability", async () => {
    mockCheckCoworkHelperHealth.mockResolvedValue({
      ok: true,
      status: "ok",
      capability: {
        mcpOk: true,
        skillsLoaded: ["/marketing-plan"],
        missingSkills: ["/marketing-generate"],
      },
    });
    renderSheet();
    await waitFor(() => expect(screen.getByText(/缺 skill：\/marketing-generate/)).toBeInTheDocument());
  });

  it("degrades gracefully when MCP is unavailable", async () => {
    mockCheckCoworkHelperHealth.mockResolvedValue({
      ok: true,
      status: "ok",
      capability: {
        mcpOk: false,
        skillsLoaded: ["/marketing-plan"],
        missingSkills: [],
      },
    });
    renderSheet();
    await waitFor(() => expect(screen.getByText(/ZenOS 連線失敗/)).toBeInTheDocument());
  });

  it("shows apply button for structured output and writes back", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ type: "capability_check", capability: { mcpOk: true, skillsLoaded: ["/marketing-plan"] } });
      onEvent({
        type: "message",
        requestId: "req-1",
        line: '{"target_field":"strategy","value":{"audience":["跑步新手"],"tone":"更直接","core_message":"先恢復頻率","platforms":["Threads"]}}',
      });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });
    const { onApply } = renderSheet();
    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 已連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    expect(screen.getByText("語氣")).toBeInTheDocument();
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1));
  });

  it("allows summarizing the conversation into a structured result", async () => {
    const { onApply } = renderSheet();
    mockStreamCoworkChat
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({ type: "capability_check", capability: { mcpOk: true, skillsLoaded: ["/marketing-plan"] } });
        onEvent({ type: "message", requestId: "req-1", line: "先聚焦跑步新手的回歸動機。" });
        onEvent({ type: "done", requestId: "req-1", code: 0 });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({
          type: "message",
          requestId: "req-2",
          line: '{"target_field":"strategy","value":{"audience":["跑步新手"],"tone":"更直接","core_message":"先恢復頻率","platforms":["Threads"]}}',
        });
        onEvent({ type: "done", requestId: "req-2", code: 0 });
      });

    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 已連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("整理結果")).toBeInTheDocument());
    fireEvent.click(screen.getByText("整理結果"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1));
    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(2);
  });

  it("shows a single missing-field warning when structured output is incomplete", async () => {
    render(
      <CoworkChatSheet
        campaignId="proj-1"
        onError={vi.fn()}
        fieldContext={{
          fieldId: "style",
          fieldLabel: "文風設定",
          currentPhase: "adapt",
          suggestedSkill: "/marketing-adapt",
          projectSummary: "官網 Blog / 長期經營",
          fieldValue: { title: "Threads 版", content: "原始文風" },
          onApply: vi.fn(async () => {}),
        }}
      />
    );

    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({
        type: "message",
        requestId: "req-1",
        line: '{"target_field":"style","value":{"title":"只有標題"}}',
      });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });

    fireEvent.click(screen.getByText("AI 討論（Beta）"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 已連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("AI 回覆還不能套用，缺少欄位：content")).toBeInTheDocument());
    expect(screen.queryByText("系統：結構化結果缺少鍵：content")).not.toBeInTheDocument();
    expect(screen.getAllByText("AI 回覆還不能套用，缺少欄位：content")).toHaveLength(1);
  });

  it("supports marketing prompt draft apply in the shared rail", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({
        type: "message",
        requestId: "req-1",
        line: '{"target_field":"marketing_prompt_draft","value":{"content":"新版 prompt draft"}}',
      });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });
    const onApply = vi.fn(async () => {});
    render(
      <CoworkChatSheet
        campaignId="proj-1"
        onError={vi.fn()}
        promptContext={{
          skill: "marketing-generate",
          title: "主文案生成",
          projectSummary: "行銷 Prompt SSOT",
          draftContent: "舊版 draft",
          publishedContent: "目前 published",
          publishedVersion: 3,
          onApply,
        }}
      />
    );
    fireEvent.click(screen.getByText("AI 討論（Beta）"));
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    expect(screen.getAllByText(/主文案生成 Draft/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() =>
      expect(onApply).toHaveBeenCalledWith({
        targetField: "marketing_prompt_draft",
        value: { content: "新版 prompt draft" },
      })
    );
  });

  it("enters the dialog with field-level context already loaded", async () => {
    renderSheet();
    expect(screen.getAllByText(/討論這段：策略設定/).length).toBeGreaterThan(0);
    expect(screen.getByText(/只保留目前欄位、project scope 和必要 context/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("查看 prompt / context"));
    expect(screen.getByText("已載入上下文清單")).toBeInTheDocument();
  });

  it("detects conflict before apply", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ type: "capability_check", capability: { mcpOk: true, skillsLoaded: ["/marketing-plan"] } });
      onEvent({
        type: "message",
        requestId: "req-1",
        line: '{"target_field":"strategy","value":{"audience":["跑步新手"],"tone":"更直接","core_message":"先恢復頻率","platforms":["Threads"]}}',
      });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const onApply = vi.fn(async () => {});
    const baseProps = {
      campaignId: "proj-1" as string | null,
      onError: vi.fn(),
    };
    const baseFieldContext = {
      fieldId: "strategy" as const,
      fieldLabel: "策略設定",
      currentPhase: "strategy" as const,
      suggestedSkill: "/marketing-plan",
      projectSummary: "官網 Blog / 長期經營",
      fieldValue: { audience: ["跑步新手"], tone: "直接" },
      onApply,
    };
    const { rerender } = render(
      <CoworkChatSheet {...baseProps} fieldContext={{ ...baseFieldContext, conflictVersion: "v1" }} />
    );
    fireEvent.click(screen.getByText("AI 討論（Beta）"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 已連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    rerender(
      <CoworkChatSheet {...baseProps} fieldContext={{ ...baseFieldContext, conflictVersion: "v2" }} />
    );
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    expect(onApply).not.toHaveBeenCalled();
  });

  it("shows retry action after stream failure", async () => {
    mockStreamCoworkChat.mockRejectedValueOnce(new Error("helper unavailable"));
    renderSheet();
    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 已連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => {
      expect(screen.getByText(/對話中斷或寫回失敗/)).toBeInTheDocument();
      expect(screen.getByText("重試上一輪")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("重試上一輪"));
    await waitFor(() => expect(mockStreamCoworkChat).toHaveBeenCalledTimes(2));
  });

  it("shows retry action after writeback failure", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ type: "capability_check", capability: { mcpOk: true, skillsLoaded: ["/marketing-plan"] } });
      onEvent({
        type: "message",
        requestId: "req-1",
        line: '{"target_field":"strategy","value":{"audience":["跑步新手"],"tone":"更直接","core_message":"先恢復頻率","platforms":["Threads"]}}',
      });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });
    const onError = vi.fn();
    const onApply = vi.fn(async () => {
      throw new Error("ZenOS write failed");
    });
    render(
      <CoworkChatSheet
        campaignId="proj-1"
        onError={onError}
        fieldContext={{
          fieldId: "strategy",
          fieldLabel: "策略設定",
          currentPhase: "strategy",
          suggestedSkill: "/marketing-plan",
          projectSummary: "官網 Blog / 長期經營",
          fieldValue: { audience: ["跑步新手"], tone: "直接" },
          conflictVersion: "v1",
          onApply,
        }}
      />
    );
    fireEvent.click(screen.getByText("AI 討論（Beta）"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Connector 已連線" })).toBeInTheDocument());
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() => {
      expect(screen.getByText(/對話中斷或寫回失敗/)).toBeInTheDocument();
      expect(screen.getByText("重試上一輪")).toBeInTheDocument();
    });
    expect(onError).toHaveBeenCalledWith("ZenOS write failed");
  });

  it("closing without apply does not write anything back", async () => {
    const { onApply, unmount } = renderSheet();
    unmount();
    expect(onApply).not.toHaveBeenCalled();
  });

  it("does not show any web-side confirm button for local permissions", async () => {
    renderSheet();
    expect(screen.queryByText(/在 Web 確認/)).not.toBeInTheDocument();
  });

  it("keeps the launcher keyboard focusable", async () => {
    render(
      <CoworkChatSheet
        campaignId="proj-1"
        onError={vi.fn()}
        fieldContext={{
          fieldId: "strategy",
          fieldLabel: "策略設定",
          currentPhase: "strategy",
          suggestedSkill: "/marketing-plan",
          projectSummary: "官網 Blog / 長期經營",
          fieldValue: { audience: ["跑步新手"], tone: "直接" },
          conflictVersion: "v1",
          onApply: vi.fn(async () => {}),
        }}
      />
    );

    const launcher = screen.getByRole("button", { name: "AI 討論（Beta）" });
    launcher.focus();
    expect(document.activeElement).toBe(launcher);
  });
});
