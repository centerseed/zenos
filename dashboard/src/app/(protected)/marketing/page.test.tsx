import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MarketingProject, MarketingStyleBuckets } from "@/lib/marketing-api";
import {
  CampaignDetail,
  CampaignList,
  CampaignStarter,
  StrategyAndPlan,
} from "@/app/(protected)/marketing/page";

afterEach(() => {
  cleanup();
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

const emptyStyles: MarketingStyleBuckets = { product: [], platform: [], project: [] };

function makeCampaign(overrides: Partial<MarketingProject> = {}): MarketingProject {
  return {
    id: "proj-1",
    name: "官網 Blog",
    description: "Paceriz 長期經營",
    status: "active",
    projectType: "long_term",
    thisWeek: { posts: 0, approved: 0, published: 0 },
    stats: { followers: "1200", postsThisMonth: 2, avgEngagement: "3.2%" },
    trend: { followers: "+24", engagement: "+0.3%" },
    posts: [],
    ...overrides,
  };
}

describe("CampaignStarter", () => {
  it("shows product picker in empty state", () => {
    render(
      <CampaignStarter
        productOptions={[{ id: "prod-1", name: "Paceriz" }]}
        creatingCampaign={false}
        onCreateCampaign={vi.fn(async () => {})}
      />
    );
    expect(screen.getByText("建立行銷項目")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Paceriz")).toBeInTheDocument();
  });
});

describe("CampaignList", () => {
  it("renders product-grouped overview", () => {
    render(
      <CampaignList
        groups={[
          {
            product: { id: "prod-1", name: "Paceriz" },
            projects: [
              makeCampaign({
                posts: [{ id: "p1", platform: "Threads", status: "draft_generated", title: "待確認", preview: "copy" }],
              }),
            ],
          },
        ]}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText("Paceriz")).toBeInTheDocument();
    expect(screen.getByText("官網 Blog")).toBeInTheDocument();
    expect(screen.getByText(/1 篇貼文/)).toBeInTheDocument();
  });
});

describe("CampaignDetail", () => {
  it("shows a single primary CTA and keeps topic creation locked before strategy", () => {
    render(
      <CampaignDetail
        campaign={makeCampaign()}
        onBack={vi.fn()}
        onReview={vi.fn()}
        reviewingPostId={null}
        onSaveContentPlan={vi.fn(async () => {})}
        savingPlan={false}
        onCreateTopic={vi.fn(async () => {})}
        creatingTopic={false}
        onSaveStrategy={vi.fn(async () => {})}
        onError={vi.fn()}
        savingStrategy={false}
        styles={emptyStyles}
        onSaveStyle={vi.fn(async () => {})}
        savingStyle={false}
      />
    );

    expect(screen.getByText("先完成策略")).toBeInTheDocument();
    expect(screen.getByText(/先完成策略設定，再建立主題與排程/)).toBeInTheDocument();
    expect(screen.queryByText("建立行銷主題")).not.toBeInTheDocument();
  });

  it("keeps pending review above published content in the detail flow", () => {
    render(
      <CampaignDetail
        campaign={makeCampaign({
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
          posts: [
            { id: "p1", platform: "Threads", status: "draft_generated", title: "待確認", preview: "copy" },
            { id: "p2", platform: "Threads", status: "published", title: "已發佈", preview: "copy" },
          ],
        })}
        onBack={vi.fn()}
        onReview={vi.fn()}
        reviewingPostId={null}
        onSaveContentPlan={vi.fn(async () => {})}
        savingPlan={false}
        onCreateTopic={vi.fn(async () => {})}
        creatingTopic={false}
        onSaveStrategy={vi.fn(async () => {})}
        onError={vi.fn()}
        savingStrategy={false}
        styles={emptyStyles}
        onSaveStyle={vi.fn(async () => {})}
        savingStyle={false}
      />
    );

    const headings = screen.getAllByRole("heading", { level: 3 });
    const reviewHeading = headings.find((node) => node.textContent === "待你確認");
    const publishedHeading = headings.find((node) => node.textContent === "已發佈");
    expect(reviewHeading).toBeTruthy();
    expect(publishedHeading).toBeTruthy();
    expect(reviewHeading!.compareDocumentPosition(publishedHeading!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("uses a dual-column layout on desktop breakpoints", () => {
    render(
      <CampaignDetail
        campaign={makeCampaign({
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
        })}
        onBack={vi.fn()}
        onReview={vi.fn()}
        reviewingPostId={null}
        onSaveContentPlan={vi.fn(async () => {})}
        savingPlan={false}
        onCreateTopic={vi.fn(async () => {})}
        creatingTopic={false}
        onSaveStrategy={vi.fn(async () => {})}
        onError={vi.fn()}
        savingStrategy={false}
        styles={emptyStyles}
        onSaveStyle={vi.fn(async () => {})}
        savingStyle={false}
      />
    );

    expect(screen.getByTestId("campaign-detail-layout").className).toContain("xl:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]");
  });

  it("guides the first success path from strategy to planning to first topic", () => {
    render(
      <CampaignDetail
        campaign={makeCampaign({
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
          contentPlan: [
            {
              weekLabel: "Week 1",
              isCurrent: true,
              days: [{ day: "Mon", platform: "Threads", topic: "主題 A", status: "suggested" }],
              aiNote: "先從暖身切入",
            },
          ],
          posts: [{ id: "p1", platform: "Threads", status: "topic_planned", title: "主題 A", preview: "copy" }],
        })}
        onBack={vi.fn()}
        onReview={vi.fn()}
        reviewingPostId={null}
        onSaveContentPlan={vi.fn(async () => {})}
        savingPlan={false}
        onCreateTopic={vi.fn(async () => {})}
        creatingTopic={false}
        onSaveStrategy={vi.fn(async () => {})}
        onError={vi.fn()}
        savingStrategy={false}
        styles={emptyStyles}
        onSaveStyle={vi.fn(async () => {})}
        savingStyle={false}
      />
    );

    expect(screen.getByText("先補情報")).toBeInTheDocument();
    expect(screen.getByText(/主題已建立，先跑 \/marketing-intel/)).toBeInTheDocument();
  });

  it("shows failure reason and next action", () => {
    render(
      <CampaignDetail
        campaign={makeCampaign({
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
          posts: [{ id: "p1", platform: "Threads", status: "failed", title: "失敗貼文", preview: "copy", aiReason: "helper 中斷" }],
        })}
        onBack={vi.fn()}
        onReview={vi.fn()}
        reviewingPostId={null}
        onSaveContentPlan={vi.fn(async () => {})}
        savingPlan={false}
        onCreateTopic={vi.fn(async () => {})}
        creatingTopic={false}
        onSaveStrategy={vi.fn(async () => {})}
        onError={vi.fn()}
        savingStrategy={false}
        styles={emptyStyles}
        onSaveStyle={vi.fn(async () => {})}
        savingStyle={false}
      />
    );
    expect(screen.getByText("AI 流程中斷")).toBeInTheDocument();
    expect(screen.getByText("helper 中斷")).toBeInTheDocument();
  });

  it("shows strategy, schedule and grouped post sections when data exists", () => {
    render(
      <CampaignDetail
        campaign={makeCampaign({
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
          contentPlan: [
            {
              weekLabel: "Week 1",
              isCurrent: true,
              days: [{ day: "Mon", platform: "Threads", topic: "主題 A", status: "suggested" }],
              aiNote: "先從暖身切入",
            },
          ],
          posts: [
            { id: "p1", platform: "Threads", status: "draft_generated", title: "待確認", preview: "copy" },
            { id: "p2", platform: "Threads", status: "published", title: "已發佈", preview: "copy" },
          ],
        })}
        onBack={vi.fn()}
        onReview={vi.fn()}
        reviewingPostId={null}
        onSaveContentPlan={vi.fn(async () => {})}
        savingPlan={false}
        onCreateTopic={vi.fn(async () => {})}
        creatingTopic={false}
        onSaveStrategy={vi.fn(async () => {})}
        onError={vi.fn()}
        savingStrategy={false}
        styles={emptyStyles}
        onSaveStyle={vi.fn(async () => {})}
        savingStyle={false}
      />
    );

    expect(screen.getByText("建立行銷寫作計畫")).toBeInTheDocument();
    expect(screen.getByText("內容排程")).toBeInTheDocument();
    expect(screen.getByText("待你確認")).toBeInTheDocument();
    expect(screen.getAllByText("已發佈").length).toBeGreaterThan(0);
    expect(screen.getByText("建立行銷主題")).toBeInTheDocument();
  });
});

describe("StrategyAndPlan", () => {
  it("lets users adjust the content plan and save it", async () => {
    const onSavePlan = vi.fn(async () => {});
    render(
      <StrategyAndPlan
        campaign={makeCampaign()}
        strategy={{
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
        }}
        contentPlan={[
          {
            weekLabel: "Week 1",
            isCurrent: true,
            days: [{ day: "Mon", platform: "Threads", topic: "主題 A", status: "suggested" }],
            aiNote: "先從暖身切入",
          },
        ]}
        posts={[]}
        onSavePlan={onSavePlan}
        savingPlan={false}
        onError={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText("調整排程"));
    fireEvent.change(screen.getByDisplayValue("主題 A"), { target: { value: "主題 B" } });
    fireEvent.click(screen.getByText("儲存排程"));

    await waitFor(() =>
      expect(onSavePlan).toHaveBeenCalledWith([
        {
          weekLabel: "Week 1",
          isCurrent: true,
          days: [{ day: "Mon", platform: "Threads", topic: "主題 B", status: "suggested" }],
          aiNote: "先從暖身切入",
        },
      ])
    );
  });

  it("warns before deleting a topic that already entered content generation", () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    render(
      <StrategyAndPlan
        campaign={makeCampaign()}
        strategy={{
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
        }}
        contentPlan={[
          {
            weekLabel: "Week 1",
            isCurrent: true,
            days: [{ day: "Mon", platform: "Threads", topic: "主題 A", status: "suggested" }],
            aiNote: "先從暖身切入",
          },
        ]}
        posts={[{ id: "p1", platform: "Threads", status: "draft_generated", title: "主題 A", preview: "copy" }]}
        onSavePlan={vi.fn(async () => {})}
        savingPlan={false}
        onError={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText("調整排程"));
    fireEvent.click(screen.getByText("刪除"));

    expect(alertSpy).toHaveBeenCalledWith("這個主題已進入內容生成流程，不能直接刪除；請先處理進行中的貼文。");
  });

  it("offers field-level discussion for schedule planning", () => {
    render(
      <StrategyAndPlan
        campaign={makeCampaign()}
        strategy={{
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
        }}
        contentPlan={[
          {
            weekLabel: "Week 1",
            isCurrent: true,
            days: [{ day: "Mon", platform: "Threads", topic: "主題 A", status: "suggested" }],
            aiNote: "先從暖身切入",
          },
        ]}
        posts={[]}
        onSavePlan={vi.fn(async () => {})}
        savingPlan={false}
        onError={vi.fn()}
      />
    );

    expect(screen.getByText("帶進 AI")).toBeInTheDocument();
  });
});
