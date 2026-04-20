import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockCheckCoworkHelperHealth = vi.fn();
const mockStreamCoworkChat = vi.fn();
const mockCancelCoworkRequest = vi.fn();
const mockCreateAiInsight = vi.fn();
const mockUpdateBriefing = vi.fn();

vi.mock("@/lib/cowork-helper", () => ({
  streamCoworkChat: (...args: unknown[]) => mockStreamCoworkChat(...args),
  cancelCoworkRequest: (...args: unknown[]) => mockCancelCoworkRequest(...args),
  checkCoworkHelperHealth: (...args: unknown[]) => mockCheckCoworkHelperHealth(...args),
  getDefaultHelperBaseUrl: () => "http://127.0.0.1:4317",
  getDefaultHelperToken: () => "",
  getDefaultHelperModel: () => "sonnet",
  getDefaultHelperCwd: () => "/tmp/workspace",
}));

vi.mock("@/components/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("@/lib/crm-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/crm-api")>("@/lib/crm-api");
  return {
    ...actual,
    createAiInsight: (...args: unknown[]) => mockCreateAiInsight(...args),
    updateBriefing: (...args: unknown[]) => mockUpdateBriefing(...args),
    patchDealStage: vi.fn(),
  };
});

import { CrmAiPanel } from "@/app/(protected)/clients/deals/[id]/CrmAiPanel";

beforeEach(() => {
  mockCheckCoworkHelperHealth.mockResolvedValue({
    ok: true,
    status: "ok",
    capability: null,
  });
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText: vi.fn(async () => {}) },
    configurable: true,
  });
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    value: vi.fn(),
    configurable: true,
  });
  mockCreateAiInsight.mockResolvedValue({
    id: "briefing-1",
    dealId: "deal-1",
    activityId: null,
    insightType: "briefing",
    content: "第一輪摘要",
    metadata: { title: "會議準備" },
    status: "active",
    createdAt: "2026-04-15T00:00:00Z",
  });
  mockUpdateBriefing.mockResolvedValue({
    id: "briefing-1",
    dealId: "deal-1",
    activityId: null,
    insightType: "briefing",
    content: "第二輪補充",
    metadata: { title: "會議準備" },
    status: "active",
    createdAt: "2026-04-15T00:00:00Z",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderPanel() {
  return render(
    <CrmAiPanel
      mode="briefing"
      deal={{
        id: "deal-1",
        partnerId: "partner-1",
        title: "企業流程導入",
        companyId: "company-1",
        ownerPartnerId: "owner-1",
        funnelStage: "需求訪談",
        deliverables: [],
        isClosedLost: false,
        isOnHold: false,
        createdAt: new Date("2026-04-01T00:00:00Z"),
        updatedAt: new Date("2026-04-01T00:00:00Z"),
      }}
      activities={[]}
      company={null}
      contacts={[]}
      token="token"
    />
  );
}

function renderDebriefPanel() {
  return render(
    <CrmAiPanel
      mode="debrief"
      deal={{
        id: "deal-1",
        partnerId: "partner-1",
        title: "企業流程導入",
        companyId: "company-1",
        ownerPartnerId: "owner-1",
        funnelStage: "需求訪談",
        deliverables: [],
        isClosedLost: false,
        isOnHold: false,
        createdAt: new Date("2026-04-01T00:00:00Z"),
        updatedAt: new Date("2026-04-01T00:00:00Z"),
      }}
      activities={[]}
      company={null}
      contacts={[]}
      token="token"
      triggerActivity={{
        id: "activity-1",
        dealId: "deal-1",
        partnerId: "partner-1",
        activityType: "會議",
        activityAt: new Date("2026-04-15T00:00:00Z"),
        summary: "本次會議摘要",
        recordedBy: "owner-1",
        isSystem: false,
        createdAt: new Date("2026-04-15T00:00:00Z"),
      }}
    />
  );
}

describe("CrmAiPanel", () => {
  it("auto-starts the first briefing turn when the panel opens and uses continue for follow-ups", async () => {
    mockStreamCoworkChat
      .mockImplementationOnce(async ({ mode, onEvent }) => {
        expect(mode).toBe("start");
        onEvent({ type: "message", requestId: "req-1", line: '{"text":"第一輪摘要"}' });
        onEvent({ type: "done", requestId: "req-1", code: 0 });
      })
      .mockImplementationOnce(async ({ mode, onEvent }) => {
        expect(mode).toBe("continue");
        onEvent({ type: "message", requestId: "req-2", line: '{"text":"第二輪補充"}' });
        onEvent({ type: "done", requestId: "req-2", code: 0 });
      });

    renderPanel();

    await waitFor(() => expect(screen.getByText("第一輪摘要")).toBeInTheDocument());
    await waitFor(() => expect(mockCreateAiInsight).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("準備下次會議")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("追問或調整重點..."), {
      target: { value: "請再補充客戶痛點" },
    });
    fireEvent.click(screen.getByText("送出"));

    await waitFor(() => expect(screen.getByText("第二輪補充")).toBeInTheDocument());
    await waitFor(() => expect(mockUpdateBriefing).toHaveBeenCalledTimes(1));
    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(2);
  });

  it("shows helper stderr when a follow-up turn exits with non-zero code", async () => {
    mockStreamCoworkChat
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({ type: "message", requestId: "req-1", line: '{"text":"第一輪摘要"}' });
        onEvent({ type: "done", requestId: "req-1", code: 0 });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({ type: "stderr", requestId: "req-2", text: "permission denied" });
        onEvent({ type: "done", requestId: "req-2", code: 1 });
      });

    renderPanel();

    await waitFor(() => expect(screen.getByText("第一輪摘要")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("追問或調整重點..."), {
      target: { value: "請再補充客戶痛點" },
    });
    fireEvent.click(screen.getByText("送出"));

    await waitFor(() => expect(screen.getByText("permission denied")).toBeInTheDocument());
  });

  it("renders nested stream_event payloads from helper responses", async () => {
    mockStreamCoworkChat.mockImplementationOnce(async ({ onEvent }) => {
      onEvent({
        type: "message",
        requestId: "req-1",
        line: '{"type":"stream_event","event":{"message":{"content":[{"content":{"text":"第一輪摘要"}}]}}}',
      });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("第一輪摘要")).toBeInTheDocument());
  });

  it("does not send follow-up on plain Enter, but sends on Ctrl+Enter", async () => {
    mockStreamCoworkChat
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({ type: "message", requestId: "req-1", line: '{"text":"第一輪摘要"}' });
        onEvent({ type: "done", requestId: "req-1", code: 0 });
      })
      .mockImplementationOnce(async ({ mode, onEvent }) => {
        expect(mode).toBe("continue");
        onEvent({ type: "message", requestId: "req-2", line: '{"text":"第二輪補充"}' });
        onEvent({ type: "done", requestId: "req-2", code: 0 });
      });

    renderPanel();

    await waitFor(() => expect(screen.getByText("第一輪摘要")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("追問或調整重點...");
    fireEvent.change(input, { target: { value: "先不要送出" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(1);
    expect(screen.getByDisplayValue("先不要送出")).toBeInTheDocument();

    fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });

    await waitFor(() => expect(screen.getByText("第二輪補充")).toBeInTheDocument());
    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(2);
  });

  it("shows shared shell warnings for capability and permission events", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({
        type: "capability_check",
        capability: {
          mcpOk: false,
          skillsLoaded: [],
          missingSkills: ["/crm-briefing"],
        },
      });
      onEvent({
        type: "permission_request",
        requestId: "req-1",
        request: { toolName: "mcp__zenos__search", timeoutSeconds: 30 },
      });
    });

    renderPanel();

    await waitFor(() =>
      expect(screen.getAllByText(/等待本機確認：mcp__zenos__search/).length).toBeGreaterThan(0)
    );
    expect(screen.getByText("ZenOS 連線失敗")).toBeInTheDocument();
    expect(screen.getByText("缺 skill：/crm-briefing")).toBeInTheDocument();
  });

  it("sends helper cancel request when briefing stream is cancelled", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent, signal }) => {
      onEvent({ type: "message", requestId: "req-1", line: '{"text":"串流中"}' });
      await new Promise((_resolve, reject) => {
        signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("取消")).toBeInTheDocument());
    fireEvent.click(screen.getByText("取消"));

    await waitFor(() =>
      expect(mockCancelCoworkRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          requestId: "req-1",
        })
      )
    );
  });

  it("shows debrief progress copy before the first streamed token arrives", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ signal }) => {
      await new Promise((_resolve, reject) => {
        signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    renderDebriefPanel();

    await waitFor(() =>
      expect(screen.getByText("helper 已啟動，這一輪會先整理本次活動、既有 briefing 與承諾事項，再輸出 debrief。")).toBeInTheDocument()
    );
  });
});
