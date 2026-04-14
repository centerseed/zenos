import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockCheckCoworkHelperHealth = vi.fn();
const mockStreamCoworkChat = vi.fn();
const mockCancelCoworkRequest = vi.fn();

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

import { CoworkChatSheet } from "@/app/marketing/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
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
    expect(screen.getByText(/已預載欄位上下文/)).toBeInTheDocument();
    expect(screen.getByText("已載入上下文清單")).toBeInTheDocument();
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
    fireEvent.click(screen.getByText("檢查 helper"));
    await waitFor(() => {
      expect(screen.getByText(/helper 目前不可用/)).toBeInTheDocument();
      expect(screen.getByText("啟動 helper")).toBeInTheDocument();
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
    fireEvent.click(screen.getByText("檢查 helper"));
    await waitFor(() => {
      expect(screen.getByText(/部分 skill 未載入/)).toBeInTheDocument();
    });
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
    fireEvent.click(screen.getByText("檢查 helper"));
    await waitFor(() => {
      expect(screen.getByText(/ZenOS 連線失敗/)).toBeInTheDocument();
    });
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
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1));
  });

  it("enters the dialog with field-level context already loaded", async () => {
    renderSheet();
    expect(screen.getByText(/討論這段：策略設定/)).toBeInTheDocument();
    expect(screen.getByText("已載入上下文清單")).toBeInTheDocument();
    expect(screen.getByText(/官網 Blog \/ 長期經營/)).toBeInTheDocument();
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
    const { rerender } = render(
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
          onApply,
        }}
      />
    );
    fireEvent.click(screen.getByText("AI 討論（Beta）"));
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => expect(screen.getByText("套用到欄位")).toBeInTheDocument());
    rerender(
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
          conflictVersion: "v2",
          onApply,
        }}
      />
    );
    fireEvent.click(screen.getByText("套用到欄位"));
    await waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    expect(onApply).not.toHaveBeenCalled();
  });

  it("shows retry action after stream failure", async () => {
    mockStreamCoworkChat.mockRejectedValueOnce(new Error("helper unavailable"));
    renderSheet();
    fireEvent.click(screen.getByText("開始討論"));
    await waitFor(() => {
      expect(screen.getByText(/對話中斷或寫回失敗/)).toBeInTheDocument();
      expect(screen.getByText("重試上一輪")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("重試上一輪"));
    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(2);
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
