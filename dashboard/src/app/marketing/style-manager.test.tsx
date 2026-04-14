import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MarketingProject, MarketingStyleBuckets } from "@/lib/marketing-api";

const mockStreamCoworkChat = vi.fn();

vi.mock("@/lib/cowork-helper", () => ({
  cancelCoworkRequest: vi.fn(),
  checkCoworkHelperHealth: vi.fn(),
  streamCoworkChat: (...args: unknown[]) => mockStreamCoworkChat(...args),
  getDefaultHelperBaseUrl: () => "http://127.0.0.1:4317",
  getDefaultHelperToken: () => "helper-token",
  getDefaultHelperCwd: () => "/tmp/workspace",
  getDefaultHelperModel: () => "sonnet",
  setDefaultHelperBaseUrl: vi.fn(),
  setDefaultHelperToken: vi.fn(),
  setDefaultHelperCwd: vi.fn(),
  setDefaultHelperModel: vi.fn(),
}));

import { StyleManager } from "@/app/marketing/page";

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
});

const campaign: MarketingProject = {
  id: "proj-1",
  name: "官網 Blog",
  description: "Paceriz 長期經營",
  status: "active",
  projectType: "long_term",
  thisWeek: { posts: 0, approved: 0, published: 0 },
  stats: { followers: "1200", postsThisMonth: 2, avgEngagement: "3.2%" },
  trend: { followers: "+24", engagement: "+0.3%" },
  posts: [{ id: "p1", platform: "Threads", status: "topic_planned", title: "跑步新手暖身", preview: "copy" }],
  contentPlan: [
    {
      weekLabel: "Week 1",
      isCurrent: true,
      days: [{ day: "Mon", platform: "Threads", topic: "跑步新手暖身", status: "suggested" }],
      aiNote: "先從暖身切入",
    },
  ],
  strategy: {
    documentId: "doc-1",
    audience: ["跑步新手"],
    tone: "直接",
    coreMessage: "先建立習慣",
    platforms: ["Threads"],
    frequency: "每週 2 篇",
    contentMix: { education: 70, product: 30 },
    campaignGoal: "",
    ctaStrategy: "",
    referenceMaterials: [],
  },
};

const styles: MarketingStyleBuckets = {
  product: [{ id: "s1", title: "產品", level: "product", content: "# Product\n- 專業直接" }],
  platform: [{ id: "s2", title: "Threads", level: "platform", platform: "threads", content: "# Threads\n- 150 字內" }],
  project: [],
};

describe("StyleManager", () => {
  it("runs preview against local helper and shows a generated sample", async () => {
    mockStreamCoworkChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ type: "message", requestId: "req-1", line: '{"type":"content_block_delta","delta":{"text":"這是一段預覽文案"}}' });
      onEvent({ type: "done", requestId: "req-1", code: 0 });
    });

    render(
      <StyleManager
        campaign={campaign}
        styles={styles}
        onSaveStyle={vi.fn(async () => {})}
        onError={vi.fn()}
        saving={false}
      />
    );

    fireEvent.click(screen.getAllByRole("button", { name: "預覽測試" })[0]);

    await waitFor(() => {
      expect(screen.getByText("這是一段預覽文案")).toBeInTheDocument();
    });
    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(1);
    expect(mockStreamCoworkChat.mock.calls[0][0].prompt).toContain("跑步新手暖身");
  });

  it("supports iterative edit then preview again with the new style draft", async () => {
    mockStreamCoworkChat
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({ type: "message", requestId: "req-1", line: '{"type":"content_block_delta","delta":{"text":"第一版預覽"}}' });
        onEvent({ type: "done", requestId: "req-1", code: 0 });
      })
      .mockImplementationOnce(async ({ onEvent }) => {
        onEvent({ type: "message", requestId: "req-2", line: '{"type":"content_block_delta","delta":{"text":"第二版預覽"}}' });
        onEvent({ type: "done", requestId: "req-2", code: 0 });
      });

    render(
      <StyleManager
        campaign={campaign}
        styles={styles}
        onSaveStyle={vi.fn(async () => {})}
        onError={vi.fn()}
        saving={false}
      />
    );

    fireEvent.change(screen.getByPlaceholderText("文風標題"), { target: { value: "Threads 教練風" } });
    fireEvent.change(screen.getByPlaceholderText("輸入 markdown 文風內容"), {
      target: { value: "# 語氣\n- 更像教練朋友\n- 直接" },
    });

    fireEvent.click(screen.getAllByRole("button", { name: "預覽測試" })[0]);
    await waitFor(() => expect(screen.getByText("第一版預覽")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("輸入 markdown 文風內容"), {
      target: { value: "# 語氣\n- 更像教練朋友\n- 更短句" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "預覽測試" })[0]);

    await waitFor(() => expect(screen.getByText("第二版預覽")).toBeInTheDocument());
    expect(mockStreamCoworkChat).toHaveBeenCalledTimes(2);
    expect(mockStreamCoworkChat.mock.calls[1][0].prompt).toContain("更短句");
  });
});
