import type { ProjectProgressResponse } from "@/lib/api";
import type { ProjectAgentPreset, ProjectNextStepOption } from "@/features/projects/types";

const PRESET_HEADERS: Record<ProjectAgentPreset, string> = {
  claude_code: "Continue this product slice in Claude Code. Treat the project context below as source-of-truth.",
  codex: "Continue this product slice in Codex. Use the project context below directly and preserve the stated next step.",
};

function collectBlockers(progress: ProjectProgressResponse): string[] {
  const blockers = new Set<string>();
  for (const group of progress.open_work_groups) {
    for (const task of group.tasks) {
      if (task.blocked) {
        blockers.add(`${task.title}${task.blocked_reason ? ` — ${task.blocked_reason}` : ""}`);
      }
      for (const subtask of task.subtasks) {
        if (subtask.blocked) {
          blockers.add(`${subtask.title}${subtask.blocked_reason ? ` — ${subtask.blocked_reason}` : ""}`);
        }
      }
    }
  }
  return Array.from(blockers);
}

export function deriveProjectNextStepOptions(
  progress: ProjectProgressResponse
): ProjectNextStepOption[] {
  const options: ProjectNextStepOption[] = [];
  const seen = new Set<string>();

  for (const plan of progress.active_plans) {
    for (const task of plan.next_tasks) {
      if (!task.title || seen.has(task.title)) continue;
      seen.add(task.title);
      options.push({
        value: task.title,
        label: `${plan.goal} · ${task.title}`,
      });
    }
  }

  if (options.length === 0) {
    options.push({
      value: `Review current progress for ${progress.project.name}`,
      label: "Review current progress",
    });
  }

  return options;
}

export function buildFallbackRecap(progress: ProjectProgressResponse): string {
  const activePlans = progress.active_plans.length;
  const blockers = collectBlockers(progress).length;
  const milestones = progress.milestones.slice(0, 2).map((item) => item.name).join(" / ") || "none";
  return [
    `Current status: ${progress.project.name} has ${activePlans} active plan(s).`,
    `Primary stage: ${milestones}.`,
    `Known blockers: ${blockers}.`,
    `Recent movement: ${progress.recent_progress[0]?.title || "No recent progress yet."}`,
  ].join(" ");
}

export function buildProjectContinuationPrompt(
  progress: ProjectProgressResponse,
  options: {
    preset: ProjectAgentPreset;
    recap?: string | null;
    nextStep: string;
  }
): string {
  const activePlans = progress.active_plans.length
    ? progress.active_plans.map((plan) =>
        `- ${plan.goal} (${plan.status})${plan.milestones.length ? ` · milestone: ${plan.milestones.map((milestone) => milestone.name).join(", ")}` : ""} — open ${plan.open_count}, blocked ${plan.blocked_count}, review ${plan.review_count}`
      ).join("\n")
    : "- No active plans";

  const groupedOpenWork = progress.open_work_groups.length
    ? progress.open_work_groups.map((group) => {
        const tasks = group.tasks.map((task) => `  - ${task.title}${task.overdue ? " [overdue]" : ""}${task.blocked ? " [blocked]" : ""}${task.status === "review" ? " [review]" : ""}`).join("\n");
        return `- ${group.plan_goal || "Unassigned work"}\n${tasks}`;
      }).join("\n")
    : "- No open work";

  const blockers = collectBlockers(progress);
  const recap = (options.recap || "").trim() || buildFallbackRecap(progress);

  return [
    PRESET_HEADERS[options.preset],
    "",
    `Project: ${progress.project.name}`,
    `Summary: ${progress.project.summary || "No product summary provided."}`,
    "",
    "[Active Plans]",
    activePlans,
    "",
    "[Open Work]",
    groupedOpenWork,
    "",
    "[Blockers]",
    blockers.length ? blockers.map((item) => `- ${item}`).join("\n") : "- No active blockers",
    "",
    "[AI Recap]",
    recap,
    "",
    "[Next Step]",
    options.nextStep,
  ].join("\n");
}
