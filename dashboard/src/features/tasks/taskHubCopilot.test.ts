import { describe, expect, it } from "vitest";
import { buildTaskHubCopilotEntry } from "@/features/tasks/taskHubCopilot";
import type { TaskHubSnapshot } from "@/features/tasks/taskHub";

function makeSnapshot(): TaskHubSnapshot {
  return {
    summary: {
      productCount: 1,
      activeMilestoneCount: 0,
      activePlanCount: 0,
      blockedPlanCount: 0,
      overdueWorkCount: 0,
    },
    products: [],
    radar: [],
    recentChanges: [],
  };
}

describe("task hub copilot entry", () => {
  it("uses ephemeral sessions for artifact recaps to avoid replaying prior helper replies", () => {
    const entry = buildTaskHubCopilotEntry({
      snapshot: makeSnapshot(),
      workspaceId: "ws-1",
    });

    expect(entry.mode).toBe("artifact");
    expect(entry.session_policy).toBe("ephemeral");
  });
});
