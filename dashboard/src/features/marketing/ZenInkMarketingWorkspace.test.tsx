import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockGetMarketingProjectGroups = vi.fn();
const mockGetMarketingProjectDetail = vi.fn();
const mockGetMarketingProjectStyles = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      getIdToken: vi.fn(async () => "token"),
    },
  }),
}));

vi.mock("@/lib/marketing-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/marketing-api")>("@/lib/marketing-api");
  return {
    ...actual,
    getMarketingProjectGroups: (...args: unknown[]) => mockGetMarketingProjectGroups(...args),
    getMarketingProjectDetail: (...args: unknown[]) => mockGetMarketingProjectDetail(...args),
    getMarketingProjectStyles: (...args: unknown[]) => mockGetMarketingProjectStyles(...args),
    updateMarketingProjectStrategy: vi.fn(),
    createMarketingStyle: vi.fn(),
    updateMarketingStyle: vi.fn(),
  };
});

vi.mock("@/features/marketing/MarketingWorkspace", () => ({
  CoworkChatSheet: ({
    fieldContext,
    promptContext,
  }: {
    fieldContext?: { fieldLabel?: string };
    promptContext?: { title?: string };
  }) => (
    <div>
      <div>Mock AI Rail</div>
      <div>{fieldContext?.fieldLabel ? `field:${fieldContext.fieldLabel}` : "field:empty"}</div>
      <div>{promptContext?.title ? `prompt:${promptContext.title}` : "prompt:empty"}</div>
    </div>
  ),
  PromptManagerSheet: ({
    onOpenPromptCopilot,
  }: {
    onOpenPromptCopilot: (config: {
      title: string;
      skill: string;
      projectSummary: string;
      draftContent: string;
      publishedContent: string;
      publishedVersion: number;
    }) => void;
  }) => (
    <button
      onClick={() =>
        onOpenPromptCopilot({
          title: "Generate Prompt",
          skill: "marketing-generate",
          projectSummary: "Prompt SSOT",
          draftContent: "draft",
          publishedContent: "published",
          publishedVersion: 3,
        })
      }
    >
      Mock Prompt Manager
    </button>
  ),
}));

import ZenInkMarketingWorkspace from "@/features/marketing/ZenInkMarketingWorkspace";

describe("ZenInkMarketingWorkspace", () => {
  beforeEach(() => {
    mockGetMarketingProjectGroups.mockResolvedValue([
      {
        product: { id: "product-1", name: "Paceriz" },
        projects: [
          {
            id: "project-1",
            productId: "product-1",
            name: "官網 Blog",
            description: "長期內容經營",
            status: "active",
            projectType: "long_term",
            strategy: null,
            contentPlan: [],
            posts: [],
          },
        ],
      },
    ]);
    mockGetMarketingProjectDetail.mockResolvedValue({
      id: "project-1",
      productId: "product-1",
      name: "官網 Blog",
      description: "長期內容經營",
      status: "active",
      projectType: "long_term",
      strategy: {
        audience: ["跑步新手"],
        tone: "專業但親切",
        coreMessage: "先建立習慣",
        platforms: ["Threads"],
        frequency: "每週 2 篇",
        contentMix: { education: 70, product: 30 },
        ctaStrategy: "下載試跑表",
        campaignGoal: "建立名單",
        referenceMaterials: [],
        updatedAt: "2026-04-19T00:00:00Z",
      },
      contentPlan: [],
      posts: [],
    });
    mockGetMarketingProjectStyles.mockResolvedValue({
      product: [],
      platform: [],
      project: [],
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("wires the strategy launcher into the shared AI rail", async () => {
    render(<ZenInkMarketingWorkspace />);

    await waitFor(() => expect(screen.getByText("官網 Blog")).toBeInTheDocument());
    fireEvent.click(screen.getByText("官網 Blog"));

    await waitFor(() => expect(screen.getByText("Mock AI Rail")).toBeInTheDocument());
    fireEvent.click(screen.getByText("先帶進 AI —"));

    await waitFor(() => expect(screen.getByText("field:策略設定")).toBeInTheDocument());
  });

  it("opens prompt draft copilot from the Zen Ink header", async () => {
    render(<ZenInkMarketingWorkspace />);

    await waitFor(() => expect(screen.getByText("官網 Blog")).toBeInTheDocument());
    fireEvent.click(screen.getByText("官網 Blog"));

    await waitFor(() => expect(screen.getByText("Mock Prompt Manager")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Mock Prompt Manager"));

    await waitFor(() => expect(screen.getByText("prompt:Generate Prompt")).toBeInTheDocument());
  });
});
