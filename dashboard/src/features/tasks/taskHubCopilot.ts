"use client";

import type { CopilotEntryConfig } from "@/lib/copilot/types";
import type { TaskHubSnapshot } from "@/features/tasks/taskHub";

export function buildTaskHubCopilotEntry(params: {
  snapshot: TaskHubSnapshot;
  workspaceId?: string;
}): CopilotEntryConfig {
  const { snapshot, workspaceId } = params;
  const topWorkspaces = snapshot.products.slice(0, 5).map((product) => ({
    workspace: product.productName,
    current_milestone: product.currentMilestone?.name ?? null,
    active_plans: product.activePlanCount,
    blocked: product.blockedCount,
    review: product.reviewCount,
    overdue: product.overdueCount,
  }));

  return {
    intent_id: "task-hub-portfolio-recap",
    title: "Task Copilot",
    description: "Discuss portfolio-level milestone, plan, risk, and drill-down priorities.",
    mode: "artifact",
    launch_behavior: "manual",
    session_policy: "ephemeral",
    claude_code_bootstrap: {
      use_project_claude_config: true,
      required_skills: ["/triage", "/zenos-capture", "skills/governance/task-governance.md"],
      governance_topics: ["task", "capture", "document"],
      verify_zenos_write: true,
      execution_contract: [
        "Obey USER_INPUT first. If USER_INPUT asks to write, save, capture, sync, or put content into ZenOS, do that action instead of producing a recap.",
        "For document capture/write requests, persist into ZenOS ontology via MCP write or /zenos-capture; local files alone do not satisfy the request.",
      ],
    },
    scope: {
      workspace_id: workspaceId,
      scope_label: "Task Hub / Portfolio Recap",
    },
    context_pack: {
      portfolio_summary: snapshot.summary,
      top_workspaces: topWorkspaces,
      radar: snapshot.radar.map((item) => ({
        title: item.title,
        subtitle: item.subtitle,
        blocked: item.blockedCount,
        review: item.reviewCount,
        overdue: item.overdueCount,
        open: item.openCount,
      })),
      recent_changes: snapshot.recentChanges.map((item) => ({
        workspace: item.productName,
        title: item.title,
        subtitle: item.subtitle,
      })),
    },
    build_prompt: (userInput) =>
      [
        `User request: ${userInput.trim() || "(empty)"}`,
        "Primary rule: answer or execute the user request above before any default recap.",
        "You are acting as the task copilot for the ZenOS Task Hub.",
        "Use the portfolio recap as the source of truth for current milestone / plan progress across workspaces.",
        "For recap requests, answer in this order:",
        "1. 哪些工作台目前最需要先看",
        "2. 哪個 milestone 或 plan 風險最高",
        "3. 下一個建議 drill-down 的工作台與原因",
        "4. 如果使用者問 blocker、review、overdue，直接指出對應工作台與 plan",
        "Keep it concise and tied to the visible recap instead of dumping every task.",
      ].join("\n"),
  };
}
