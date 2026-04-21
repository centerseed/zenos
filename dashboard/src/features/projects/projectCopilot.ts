import type { CopilotEntryConfig } from "@/lib/copilot/types";
import type { ProjectProgressResponse } from "@/lib/api";
import type { ProjectAgentPreset } from "@/features/projects/types";
import { buildFallbackRecap } from "@/features/projects/projectPrompt";

function serializePlans(progress: ProjectProgressResponse) {
  return progress.active_plans.map((plan) => ({
    goal: plan.goal,
    status: plan.status,
    milestones: plan.milestones.map((milestone) => milestone.name),
    open_count: plan.open_count,
    blocked_count: plan.blocked_count,
    review_count: plan.review_count,
    overdue_count: plan.overdue_count,
    next_tasks: plan.next_tasks.map((task) => ({
      title: task.title,
      status: task.status,
      blocked: task.blocked,
      overdue: task.overdue,
    })),
  }));
}

export function buildProjectRecapEntry(options: {
  progress: ProjectProgressResponse;
  preset: ProjectAgentPreset;
  nextStep: string;
  workspaceId?: string;
}): CopilotEntryConfig {
  const { progress, preset, nextStep, workspaceId } = options;
  const fallback = buildFallbackRecap(progress);

  return {
    intent_id: `project-progress-${preset}`,
    title: "AI Recap",
    description: "Summarize the current product progress and suggest the next decision.",
    mode: "artifact",
    launch_behavior: "manual",
    session_policy: "scoped_resume",
    suggested_skill: "/triage",
    claude_code_bootstrap: {
      use_project_claude_config: true,
      required_skills: [
        "/triage",
        "/zenos-governance",
        "skills/governance/task-governance.md",
      ],
      governance_topics: ["task"],
      verify_zenos_write: true,
      execution_contract: [
        "Use the workspace .claude/mcp.json and settings.local.json instead of assuming a global helper profile.",
        "Before any task mutation, call mcp__zenos__governance_guide for topic=task and read local task governance files when they exist.",
        "Treat the first prompt as plan-level context only; if you need task, blocker, or subtask detail, fetch it via ZenOS MCP instead of assuming it is already embedded in the prompt.",
        "For any multi-step workstream, create a real plan first; do not use a parent task as a substitute for a plan.",
        "When the user asks to create or update work, map it to the correct layer first: shared multi-step outcome -> plan, independently trackable unit -> task, true decomposition under one task -> subtask via parent_task_id.",
        "Tasks inside that workstream must carry plan_id and plan_order, and only true decomposition work may add parent_task_id for subtasks.",
        "Handle task governance strictly according to ZenOS task governance rules, including duplicate check, canonical statuses, review-before-confirm, and re-fetch verification before claiming success.",
      ],
    },
    scope: {
      workspace_id: workspaceId,
      product_id: progress.project.id,
      project: progress.project.name,
      entity_ids: [progress.project.id],
      scope_label: `${progress.project.name} / Product Progress Console`,
    },
    context_pack: {
      project: {
        id: progress.project.id,
        name: progress.project.name,
        summary: progress.project.summary,
      },
      active_plans: serializePlans(progress),
      requested_next_step: nextStep,
      fallback_recap: fallback,
    },
    build_prompt: () =>
      [
        `Prepare a ${preset === "claude_code" ? "Claude Code" : "Codex"}-ready project recap for ${progress.project.name}.`,
        "Treat the provided context as a plan-level snapshot, not a full task dump.",
        "Your output must cover these sections in order:",
        "1. 目前進度到哪裡",
        "2. 正在進行的 plans",
        "3. 主要 blockers 與風險",
        "4. 建議下一步",
        "5. 需要使用者決策的點",
        "Keep it concise but decision-oriented. Do not dump raw tasks without synthesis.",
        "If you need task governance detail or task-level evidence, use ZenOS MCP to fetch it and follow ZenOS task governance rules when reasoning about mutations.",
        "If the user asks to create or update work items, place them at the correct layer: plan vs task vs subtask, instead of flattening everything into tasks.",
        `Use this selected next step as the default recommendation unless the context clearly points to a better one: ${nextStep}.`,
        `If the project context is sparse, still explain the current state and give a concrete next step. Fallback context: ${fallback}`,
      ].join("\n"),
  };
}
