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

function serializeOpenWork(progress: ProjectProgressResponse) {
  return progress.open_work_groups.map((group) => ({
    plan_goal: group.plan_goal,
    open_count: group.open_count,
    blocked_count: group.blocked_count,
    review_count: group.review_count,
    overdue_count: group.overdue_count,
    tasks: group.tasks.map((task) => ({
      title: task.title,
      status: task.status,
      blocked: task.blocked,
      overdue: task.overdue,
      subtasks: task.subtasks.map((subtask) => ({
        title: subtask.title,
        status: subtask.status,
        blocked: subtask.blocked,
      })),
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
        "skills/governance/document-governance.md",
      ],
      governance_topics: ["task", "document"],
      verify_zenos_write: true,
      execution_contract: [
        "Use the workspace .claude/mcp.json and settings.local.json instead of assuming a global helper profile.",
        "Before any task or document mutation, call mcp__zenos__governance_guide for the relevant topic and read local governance files when they exist.",
        "Never claim plan/task/doc creation succeeded until you re-fetch the written records from ZenOS and confirm returned ids.",
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
      open_work_groups: serializeOpenWork(progress),
      milestones: progress.milestones,
      recent_progress: progress.recent_progress,
      requested_next_step: nextStep,
      fallback_recap: fallback,
    },
    build_prompt: () =>
      [
        `Prepare a ${preset === "claude_code" ? "Claude Code" : "Codex"}-ready project recap for ${progress.project.name}.`,
        "Your output must cover these sections in order:",
        "1. 目前進度到哪裡",
        "2. 正在進行的 plans",
        "3. 主要 blockers 與風險",
        "4. 建議下一步",
        "5. 需要使用者決策的點",
        "Keep it concise but decision-oriented. Do not dump raw tasks without synthesis.",
        `Use this selected next step as the default recommendation unless the context clearly points to a better one: ${nextStep}.`,
        `If the project context is sparse, still explain the current state and give a concrete next step. Fallback context: ${fallback}`,
      ].join("\n"),
  };
}
