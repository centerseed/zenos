import { describe, expect, it } from "vitest";
import {
  buildContextPack,
  buildDiscussionPrompt,
  composeStyleMarkdown,
  deriveProjectStage,
  nextChatStatus,
  parseCoworkStreamLine,
  parseStructuredApplyPayload,
  postNextStepHint,
  primaryCtaForProject,
  stylePreviewPrompt,
} from "@/app/(protected)/marketing/logic";
import type { MarketingProject, MarketingStyleBuckets } from "@/lib/marketing-api";

function makeProject(overrides: Partial<MarketingProject> = {}): MarketingProject {
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

describe("buildContextPack", () => {
  it("keeps the required six fields and truncates to 2000 chars", () => {
    const pack = buildContextPack({
      fieldId: "strategy",
      currentPhase: "strategy",
      suggestedSkill: "/marketing-plan",
      projectSummary: "A".repeat(700),
      fieldValue: { token: "sk_supersecrettokenvalue", notes: "B".repeat(1600) },
      relatedContext: "C".repeat(1200),
    });

    expect(pack.field_id).toBe("strategy");
    expect(pack.current_phase).toBe("strategy");
    expect(pack.suggested_skill).toBe("/marketing-plan");
    expect(pack.project_summary.length).toBeLessThanOrEqual(500);
    expect(pack.field_value).toContain("[REDACTED]");
    const total =
      (pack.field_value?.length || 0) +
      pack.project_summary.length +
      (pack.related_context?.length || 0);
    expect(total).toBeLessThanOrEqual(2000);
  });

  it("rebuilds a fresh context pack for a different field", () => {
    const strategyPack = buildContextPack({
      fieldId: "strategy",
      currentPhase: "strategy",
      suggestedSkill: "/marketing-plan",
      projectSummary: "官網 Blog",
      fieldValue: "策略 A",
    });
    const topicPack = buildContextPack({
      fieldId: "topic",
      currentPhase: "generate",
      suggestedSkill: "/marketing-generate",
      projectSummary: "官網 Blog",
      fieldValue: "主題 B",
    });
    expect(strategyPack.field_id).toBe("strategy");
    expect(topicPack.field_id).toBe("topic");
    expect(strategyPack.suggested_skill).not.toBe(topicPack.suggested_skill);
  });
});

describe("buildDiscussionPrompt", () => {
  it("uses guided template for empty fields", () => {
    const prompt = buildDiscussionPrompt(
      {
        fieldId: "strategy",
        fieldLabel: "策略設定",
        currentPhase: "strategy",
        suggestedSkill: "/marketing-plan",
        projectSummary: "官網 Blog / 長期經營",
        fieldValue: null,
      },
      ""
    );

    expect(prompt).toContain("請幫我設定這個項目的策略設定");
    expect(prompt).toContain("建議 skill：/marketing-plan");
  });

  it("uses revision template for existing fields", () => {
    const prompt = buildDiscussionPrompt(
      {
        fieldId: "style",
        fieldLabel: "文風設定",
        currentPhase: "adapt",
        suggestedSkill: "/marketing-adapt",
        projectSummary: "官網 Blog / 長期經營",
        fieldValue: { content: "像教練朋友一樣說話" },
      },
      "把語氣再直接一點"
    );

    expect(prompt).toContain("以下是目前的文風設定");
    expect(prompt).toContain("使用者補充：把語氣再直接一點");
  });

  it("keeps the suggested skill in the prompt contract", () => {
    const prompt = buildDiscussionPrompt(
      {
        fieldId: "review",
        fieldLabel: "審核意見",
        currentPhase: "publish",
        suggestedSkill: "/marketing-publish",
        projectSummary: "官網 Blog / 長期經營",
        fieldValue: { summary: "CTA 太弱" },
      },
      ""
    );
    expect(prompt).toContain("建議 skill：/marketing-publish");
  });
});

describe("parseStructuredApplyPayload", () => {
  it("parses valid fenced JSON", () => {
    const result = parseStructuredApplyPayload(
      '先說明\n```json\n{"target_field":"topic","value":{"title":"跑步新手","brief":"聚焦暖身迷思"}}\n```'
    );
    expect(result.missingKeys).toEqual([]);
    expect(result.payload).toEqual({
      targetField: "topic",
      value: { title: "跑步新手", brief: "聚焦暖身迷思" },
    });
  });

  it("rejects payloads with missing required keys", () => {
    const result = parseStructuredApplyPayload('{"target_field":"style","value":{"title":"只有標題"}}');
    expect(result.payload).toBeNull();
    expect(result.missingKeys).toEqual(["content"]);
  });

  it("ignores invalid JSON", () => {
    const result = parseStructuredApplyPayload("```json\n{nope}\n```");
    expect(result.payload).toBeNull();
    expect(result.missingKeys).toEqual([]);
  });
});

describe("project phase helpers", () => {
  it("derives strategy stage before strategy is saved", () => {
    const project = makeProject();
    expect(deriveProjectStage(project)).toBe("strategy");
    expect(primaryCtaForProject(project).label).toBe("先完成策略");
  });

  it("derives review stage when there is a pending draft", () => {
    const project = makeProject({
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
      posts: [{ id: "p1", platform: "Threads", status: "draft_generated", title: "主文案", preview: "copy" }],
    });
    expect(deriveProjectStage(project)).toBe("review");
    expect(primaryCtaForProject(project).label).toBe("確認文案");
  });

  it("derives schedule stage once strategy is saved but before plan exists", () => {
    const project = makeProject({
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
    });
    expect(deriveProjectStage(project)).toBe("schedule");
    expect(primaryCtaForProject(project).label).toBe("先產生排程");
  });

  it("surfaces current phase visibility and single primary CTA", () => {
    const project = makeProject({
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
      posts: [{ id: "p1", platform: "Threads", status: "topic_planned", title: "主題", preview: "copy" }],
    });
    expect(deriveProjectStage(project)).toBe("intel");
    expect(primaryCtaForProject(project)).toEqual({
      label: "先補情報",
      hint: "主題已建立，先跑 /marketing-intel 蒐集近期訊號。",
    });
  });
});

describe("postNextStepHint", () => {
  it("returns the right next steps per workflow stage", () => {
    expect(postNextStepHint({ id: "p1", platform: "Threads", status: "topic_planned", title: "t", preview: "p" })).toContain(
      "/marketing-intel"
    );
    expect(postNextStepHint({ id: "p2", platform: "Threads", status: "draft_confirmed", title: "t", preview: "p" })).toContain(
      "/marketing-adapt"
    );
    expect(postNextStepHint({ id: "p3", platform: "Threads", status: "platform_confirmed", title: "t", preview: "p" })).toContain(
      "/marketing-publish"
    );
  });
});

describe("style composition", () => {
  it("combines style layers and skips missing ones", () => {
    const styles: MarketingStyleBuckets = {
      product: [{ id: "s1", title: "產品", level: "product", content: "# Product\n- 直接" }],
      platform: [{ id: "s2", title: "Threads", level: "platform", platform: "Threads", content: "# Threads\n- 150 字內" }],
      project: [],
    };
    const merged = composeStyleMarkdown(styles, "Threads");
    expect(merged).toContain("Product Style");
    expect(merged).toContain("Platform Style");
    expect(merged).not.toContain("Project Style");

    const preview = stylePreviewPrompt({
      styles,
      topic: "跑步新手暖身",
      platform: "Threads",
      projectName: "官網 Blog",
    });
    expect(preview).toContain("跑步新手暖身");
    expect(preview).toContain("platform=Threads");
  });
});

describe("parseCoworkStreamLine", () => {
  it("extracts text deltas from stream-json", () => {
    expect(parseCoworkStreamLine('{"type":"content_block_delta","delta":{"text":"hello"}}')).toEqual({
      delta: "hello",
      debug: "",
    });
  });

  it("extracts text from stream_event wrapper (Claude CLI format)", () => {
    const line = JSON.stringify({
      type: "stream_event",
      event: { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "wrapped" } },
    });
    expect(parseCoworkStreamLine(line)).toEqual({ delta: "wrapped", debug: "" });
  });

  it("suppresses debug for stream_event with no text", () => {
    const line = JSON.stringify({
      type: "stream_event",
      event: { type: "message_start", message: { role: "assistant", content: [] } },
    });
    expect(parseCoworkStreamLine(line)).toEqual({ delta: "", debug: "" });
  });

  it("does not re-read full assistant payloads that would duplicate streamed text", () => {
    const line = JSON.stringify({
      type: "assistant",
      message: { content: [{ type: "text", text: "response" }] },
    });
    expect(parseCoworkStreamLine(line)).toEqual({ delta: "", debug: "" });
  });
});

describe("nextChatStatus", () => {
  it("follows the 7-state chat machine transitions", () => {
    expect(nextChatStatus("idle", "send")).toBe("loading");
    expect(nextChatStatus("loading", "message")).toBe("streaming");
    expect(nextChatStatus("streaming", "permission_request")).toBe("awaiting-local-approval");
    expect(nextChatStatus("awaiting-local-approval", "permission_result")).toBe("streaming");
    expect(nextChatStatus("streaming", "apply_available")).toBe("apply-ready");
    expect(nextChatStatus("apply-ready", "apply_start")).toBe("applying");
    expect(nextChatStatus("applying", "apply_done")).toBe("idle");
    expect(nextChatStatus("streaming", "error")).toBe("error");
    expect(nextChatStatus("streaming", "cancel")).toBe("idle");
  });
});
