import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createMarketingProject,
  createMarketingStyle,
  createMarketingTopic,
  getMarketingProjectDetail,
  getMarketingProjectGroups,
  getMarketingProjectStyles,
  getMarketingPrompts,
  publishMarketingPrompt,
  reviewMarketingPost,
  updateMarketingProjectStrategy,
  updateMarketingPromptDraft,
  updateMarketingStyle,
} from "@/lib/marketing-api";

const FAKE_TOKEN = "marketing-token";
const API_BASE = "https://zenos-mcp-s5oifosv3a-de.a.run.app";

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: vi.fn().mockResolvedValue(body),
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("project groups", () => {
  it("calls GET /api/marketing/projects", async () => {
    const fakeFetch = mockFetch({ groups: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getMarketingProjectGroups(FAKE_TOKEN);

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/projects`);
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(`Bearer ${FAKE_TOKEN}`);
  });

  it("returns grouped projects", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        groups: [{ product: { id: "prod-1", name: "Paceriz" }, projects: [{ id: "proj-1", name: "官網 Blog", posts: [] }] }],
      })
    );

    const groups = await getMarketingProjectGroups(FAKE_TOKEN);
    expect(groups).toHaveLength(1);
    expect(groups[0].projects[0].id).toBe("proj-1");
  });
});

describe("project detail", () => {
  it("calls GET detail endpoint", async () => {
    const fakeFetch = mockFetch({
      project: { id: "proj-1", name: "官網 Blog", posts: [] },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await getMarketingProjectDetail(FAKE_TOKEN, "proj-1");

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/projects/proj-1`);
  });
});

describe("reviewMarketingPost", () => {
  it("posts review action with JSON body", async () => {
    const fakeFetch = mockFetch({
      post: { id: "p1", status: "draft_confirmed" },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await reviewMarketingPost(FAKE_TOKEN, "p1", {
      action: "approve",
      comment: "ok",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/posts/p1/review`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      action: "approve",
      comment: "ok",
    });
  });
});

describe("createMarketingTopic", () => {
  it("posts topic payload to project topics endpoint", async () => {
    const fakeFetch = mockFetch({
      post: { id: "p2", status: "topic_planned" },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createMarketingTopic(FAKE_TOKEN, "proj-1", {
      topic: "跑步新手每週排程",
      platform: "Threads",
      brief: "主打可執行性",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/projects/proj-1/topics`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      topic: "跑步新手每週排程",
      platform: "Threads",
      brief: "主打可執行性",
    });
  });
});

describe("updateMarketingProjectStrategy", () => {
  it("puts strategy payload to strategy endpoint", async () => {
    const fakeFetch = mockFetch({
      project: { id: "proj-1", name: "官網 Blog", posts: [] },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await updateMarketingProjectStrategy(FAKE_TOKEN, "proj-1", {
      audience: ["跑步新手"],
      tone: "專業友善",
      coreMessage: "先恢復穩定跑步頻率",
      platforms: ["threads", "blog"],
      frequency: "每週 2 篇",
      contentMix: { education: 70, product: 30 },
      ctaStrategy: "引導免費試用",
      expectedUpdatedAt: "2026-04-12T09:00:00+00:00",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/projects/proj-1/strategy`);
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body as string)).toEqual({
      audience: ["跑步新手"],
      tone: "專業友善",
      coreMessage: "先恢復穩定跑步頻率",
      platforms: ["threads", "blog"],
      frequency: "每週 2 篇",
      contentMix: { education: 70, product: 30 },
      ctaStrategy: "引導免費試用",
      expectedUpdatedAt: "2026-04-12T09:00:00+00:00",
    });
  });
});

describe("createMarketingProject", () => {
  it("posts project payload to projects endpoint", async () => {
    const fakeFetch = mockFetch({
      project: { id: "proj-2", name: "Campaign 2", posts: [] },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await createMarketingProject(FAKE_TOKEN, {
      productId: "prod-1",
      name: "夏季訓練活動",
      projectType: "short_term",
      dateRange: { start: "2026-05-01", end: "2026-05-31" },
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/projects`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      productId: "prod-1",
      name: "夏季訓練活動",
      projectType: "short_term",
      dateRange: { start: "2026-05-01", end: "2026-05-31" },
    });
  });
});

describe("project styles", () => {
  it("calls GET /api/marketing/projects/{id}/styles", async () => {
    const fakeFetch = mockFetch({ styles: { product: [], platform: [], project: [] } });
    vi.stubGlobal("fetch", fakeFetch);

    await getMarketingProjectStyles(FAKE_TOKEN, "proj-1");

    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/projects/proj-1/styles`);
  });

  it("creates style document", async () => {
    const fakeFetch = mockFetch({ style: { id: "style-1", level: "project", content: "tone" } });
    vi.stubGlobal("fetch", fakeFetch);

    await createMarketingStyle(FAKE_TOKEN, {
      title: "官網 Blog 專案文風",
      level: "project",
      projectId: "proj-1",
      content: "像教練朋友一樣說話",
    });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/styles`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      title: "官網 Blog 專案文風",
      level: "project",
      projectId: "proj-1",
      content: "像教練朋友一樣說話",
    });
  });

  it("updates style document", async () => {
    const fakeFetch = mockFetch({ style: { id: "style-1", content: "new tone" } });
    vi.stubGlobal("fetch", fakeFetch);

    await updateMarketingStyle(FAKE_TOKEN, "style-1", { content: "new tone" });

    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/styles/style-1`);
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body as string)).toEqual({ content: "new tone" });
  });
});

describe("marketing prompt ssot", () => {
  it("calls GET /api/marketing/prompts", async () => {
    const fakeFetch = mockFetch({ hubId: "hub-1", prompts: [] });
    vi.stubGlobal("fetch", fakeFetch);

    await getMarketingPrompts(FAKE_TOKEN);
    const [url] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/prompts`);
  });

  it("updates draft prompt", async () => {
    const fakeFetch = mockFetch({
      prompt: { skill: "marketing-generate", draftContent: "new draft" },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await updateMarketingPromptDraft(FAKE_TOKEN, "marketing-generate", "new draft");
    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/prompts/marketing-generate/draft`);
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body as string)).toEqual({ content: "new draft" });
  });

  it("publishes prompt with sourceVersion", async () => {
    const fakeFetch = mockFetch({
      prompt: { skill: "marketing-generate", publishedVersion: 3 },
    });
    vi.stubGlobal("fetch", fakeFetch);

    await publishMarketingPrompt(FAKE_TOKEN, "marketing-generate", { sourceVersion: 1, note: "rollback" });
    const [url, options] = fakeFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/api/marketing/prompts/marketing-generate/publish`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({ sourceVersion: 1, note: "rollback" });
  });
});
