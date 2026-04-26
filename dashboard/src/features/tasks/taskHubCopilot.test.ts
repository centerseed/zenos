import { describe, expect, it } from "vitest";
import { buildTaskHubCopilotEntry } from "@/features/tasks/taskHubCopilot";
import { buildCopilotPromptEnvelope } from "@/lib/copilot/envelope";
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

  it("does not force triage when the user asks to write into ZenOS", () => {
    const entry = buildTaskHubCopilotEntry({
      snapshot: makeSnapshot(),
      workspaceId: "ws-1",
    });

    const envelope = buildCopilotPromptEnvelope(entry, "把這份文件寫進 ZenOS");

    expect(envelope).toContain("[USER_INPUT]\n把這份文件寫進 ZenOS");
    expect(envelope).toContain("Obey USER_INPUT first");
    expect(envelope).toContain("persist into ZenOS ontology");
    expect(envelope).toContain("tags {what, why, how, who}");
    expect(envelope).not.toContain("suggested_skill=/triage");
  });
});
