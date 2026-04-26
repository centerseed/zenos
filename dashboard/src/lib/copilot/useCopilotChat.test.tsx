import { cleanup, render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useCopilotChat } from "@/lib/copilot/useCopilotChat";
import type { CopilotEntryConfig } from "@/lib/copilot/types";
import { writeSessionSnapshot } from "@/lib/copilot/session";

const checkCoworkHelperHealthMock = vi.hoisted(() => vi.fn());
const streamCoworkChatMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/cowork-helper", () => ({
  streamCoworkChat: (...args: unknown[]) => streamCoworkChatMock(...args),
  cancelCoworkRequest: vi.fn(),
  checkCoworkHelperHealth: (...args: unknown[]) => checkCoworkHelperHealthMock(...args),
  getDefaultHelperBaseUrl: () => "http://127.0.0.1:4317",
  getDefaultHelperToken: () => "helper-token",
  getDefaultHelperModel: () => "sonnet",
  getDefaultHelperCwd: () => "/tmp",
}));

function makeEntry(overrides: Partial<CopilotEntryConfig> = {}): CopilotEntryConfig {
  return {
    intent_id: "project-progress-claude_code",
    title: "Task Copilot",
    mode: "chat",
    launch_behavior: "manual",
    session_policy: "scoped_resume",
    scope: {
      workspace_id: "ws-active",
      product_id: "product-1",
      scope_label: "product",
    },
    context_pack: {},
    build_prompt: (input: string) => input,
    ...overrides,
  };
}

function makeStorage(seed: Record<string, string> = {}) {
  const store = new Map(Object.entries(seed));
  return {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
    key: vi.fn((index: number) => Array.from(store.keys())[index] ?? null),
    get length() {
      return store.size;
    },
  };
}

function Probe({ entry }: { entry: CopilotEntryConfig | null }) {
  const chat = useCopilotChat(entry);
  return (
    <div>
      <div data-testid="status">{chat.status}</div>
      <div data-testid="messages">{chat.messages.map((message) => message.content).join(" | ")}</div>
      <div data-testid="streaming">{chat.streamingText}</div>
      <button onClick={() => void chat.send("請整理")}>send</button>
      <button onClick={() => void chat.send("當然要入 ZenOS")}>send followup</button>
      <button onClick={() => chat.reset()}>reset</button>
    </div>
  );
}

describe("useCopilotChat", () => {
  let storage: ReturnType<typeof makeStorage>;

  beforeEach(() => {
    checkCoworkHelperHealthMock.mockReset();
    streamCoworkChatMock.mockReset();
    checkCoworkHelperHealthMock.mockResolvedValue({
      ok: true,
      status: "ok",
      capability: null,
    });
    storage = makeStorage();
    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("hydrates scoped-resume chat snapshots on mount", async () => {
    const snapshotKey =
      "zenos.copilot.snapshot.project-progress-claude_code:ws-active:product-1";
    writeSessionSnapshot(snapshotKey, {
      messages: [
        { role: "assistant", content: "先處理 milestone A", timestamp: 1 },
      ],
      streamingText: "",
      structuredResult: null,
      missingKeys: [],
      lastError: null,
      lastSubmittedInput: "目前下一步？",
      status: "idle",
    });

    render(<Probe entry={makeEntry()} />);

    expect(await screen.findByText("先處理 milestone A")).toBeInTheDocument();
  });

  it("checks helper health with workspace scope and clears snapshot on reset", async () => {
    const snapshotKey =
      "zenos.copilot.snapshot.project-progress-claude_code:ws-active:product-1";
    writeSessionSnapshot(snapshotKey, {
      messages: [{ role: "assistant", content: "old", timestamp: 1 }],
      streamingText: "",
      structuredResult: null,
      missingKeys: [],
      lastError: null,
      lastSubmittedInput: "",
      status: "idle",
    });

    render(<Probe entry={makeEntry()} />);

    await waitFor(() => {
      expect(checkCoworkHelperHealthMock).toHaveBeenCalledWith(
        "http://127.0.0.1:4317",
        "helper-token",
        "ws-active"
      );
    });

    fireEvent.click(screen.getByText("reset"));

    expect(storage.getItem(snapshotKey)).toBeNull();
  });

  it("replaces Claude partial message snapshots instead of appending duplicates", async () => {
    streamCoworkChatMock.mockImplementation(async ({ onEvent }) => {
      onEvent({
        type: "message",
        line: '{"type":"assistant","message":{"content":[{"type":"text","text":"文件已儲存。"}]}}',
      });
      onEvent({
        type: "message",
        line: '{"type":"assistant","message":{"content":[{"type":"text","text":"文件已儲存。現在給你快照。"}]}}',
      });
      onEvent({ type: "done" });
    });

    render(<Probe entry={makeEntry({ session_policy: "ephemeral" })} />);
    fireEvent.click(screen.getByText("send"));

    await waitFor(() => {
      expect(screen.getByTestId("messages").textContent).toContain("文件已儲存。現在給你快照。");
    });
    expect(screen.getByTestId("messages").textContent).not.toContain("文件已儲存。文件已儲存。");
  });

  it("sends recent visible messages with follow-up prompts in ephemeral sessions", async () => {
    streamCoworkChatMock.mockImplementation(async ({ onEvent }) => {
      const response =
        streamCoworkChatMock.mock.calls.length === 1
          ? "已建立本機文件 panel-pricing-reference.md，內容是 Panel 報價文件。"
          : "ok";
      onEvent({
        type: "message",
        line: JSON.stringify({
          type: "assistant",
          message: { content: [{ type: "text", text: response }] },
        }),
      });
      onEvent({ type: "done" });
    });

    render(<Probe entry={makeEntry({ session_policy: "ephemeral" })} />);
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => {
      expect(screen.getByTestId("messages").textContent).toContain("panel-pricing-reference.md");
    });
    fireEvent.click(screen.getByText("send followup"));

    await waitFor(() => {
      expect(streamCoworkChatMock).toHaveBeenCalledTimes(2);
    });
    const call = streamCoworkChatMock.mock.calls[1]?.[0] as { prompt: string };
    expect(call.prompt).toContain("[RECENT_CONVERSATION]");
    expect(call.prompt).toContain("panel-pricing-reference.md");
    expect(call.prompt).toContain("[USER_INPUT]\n當然要入 ZenOS");
  });
});
