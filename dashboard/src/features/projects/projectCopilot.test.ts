import { describe, expect, it } from "vitest";
import { buildProjectRecapEntry } from "@/features/projects/projectCopilot";
import type { ProjectProgressResponse } from "@/lib/api";

function makeProgress(): ProjectProgressResponse {
  return {
    project: {
      id: "project-1",
      name: "Panel 自動化合作",
      type: "deal",
      summary: "需求訪談",
      tags: { what: [], why: "", how: "", who: [] },
      status: "active",
      parentId: null,
      details: null,
      confirmedByUser: true,
      owner: null,
      sources: [],
      visibility: "public",
      lastReviewedAt: null,
      createdAt: new Date("2026-04-26T00:00:00Z"),
      updatedAt: new Date("2026-04-26T00:00:00Z"),
    },
    active_plans: [],
    open_work_groups: [],
    milestones: [],
    recent_progress: [],
  };
}

describe("project copilot entry", () => {
  it("uses ephemeral sessions for artifact recaps to avoid replaying prior helper replies", () => {
    const entry = buildProjectRecapEntry({
      progress: makeProgress(),
      preset: "claude_code",
      nextStep: "確認下一步",
      workspaceId: "ws-1",
    });

    expect(entry.mode).toBe("artifact");
    expect(entry.session_policy).toBe("ephemeral");
  });
});
