import type { CopilotEntryConfig } from "@/lib/copilot/types";
import type { ProjectProgressResponse } from "@/lib/api";
import type { ProjectAgentPreset } from "@/features/projects/types";
import { buildFallbackRecap } from "@/features/projects/projectPrompt";
import { formatRootScopeLabel } from "@/features/projects/rootLabels";

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
    plan_status: group.plan_status,
    open_count: group.open_count,
    blocked_count: group.blocked_count,
    review_count: group.review_count,
    overdue_count: group.overdue_count,
    tasks: group.tasks.map((task) => ({
      title: task.title,
      status: task.status,
      blocked: task.blocked,
      blocked_reason: task.blocked_reason,
      overdue: task.overdue,
      subtasks: task.subtasks.map((subtask) => ({
        title: subtask.title,
        status: subtask.status,
        blocked: subtask.blocked,
        overdue: subtask.overdue,
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
    title: "Task Copilot",
    description: "Discuss this root workspace's milestones, plans, tasks, blockers, and next actions.",
    mode: "artifact",
    launch_behavior: "manual",
    session_policy: "ephemeral",
    claude_code_bootstrap: {
      use_project_claude_config: true,
      required_skills: [
        "/triage",
        "/zenos-capture",
        "/zenos-governance",
        "skills/governance/task-governance.md",
        "skills/workflows/knowledge-capture.md",
      ],
      governance_topics: ["task", "capture", "document"],
      verify_zenos_write: true,
      execution_contract: [
        "Use the workspace .claude/mcp.json and settings.local.json instead of assuming a global helper profile.",
        "Obey USER_INPUT first. If USER_INPUT asks to write, save, capture, sync, or put content into ZenOS, do that action instead of producing a recap.",
        "For document capture/write requests, persist into ZenOS ontology via MCP write or /zenos-capture; local files alone do not satisfy the request.",
        "When writing a ZenOS document, use collection=documents with data.title/name, summary, tags={what,why,how,who}, linked_entity_ids including scope.product_id, and verify the saved document by MCP search/get before reporting success.",
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
      scope_label: formatRootScopeLabel(progress.project.name),
    },
    context_pack: {
      project: {
        id: progress.project.id,
        name: progress.project.name,
        summary: progress.project.summary,
      },
      milestones: progress.milestones.map((milestone) => ({
        id: milestone.id,
        name: milestone.name,
        open_count: milestone.open_count,
      })),
      active_plans: serializePlans(progress),
      open_work_groups: serializeOpenWork(progress),
      requested_next_step: nextStep,
      fallback_recap: fallback,
    },
    build_prompt: (userInput) =>
      [
        `User request: ${userInput.trim() || "(empty)"}`,
        "Primary rule: answer or execute the user request above before any default recap.",
        "If USER_INPUT references prior content, resolve it from RECENT_CONVERSATION before acting.",
        "If the user asks to write/save/capture/register a document, create or update a ZenOS document entity linked to this root workspace and verify it with MCP get/search before claiming success.",
        "For MCP write(collection=\"documents\"), include at minimum: title/name, summary, tags {what, why, how, who}, and linked_entity_ids containing the current root entity id.",
        "If you also create a local Markdown file, clearly say it is local-only until the ZenOS document write succeeds.",
        `You are acting as the task copilot for ${progress.project.name} in ${preset === "claude_code" ? "Claude Code" : "Codex"}.`,
        "Treat the provided context as the current milestone / plan / task snapshot for this root workspace.",
        "For recap requests, cover these sections in order:",
        "1. 目前所在 milestone / 階段",
        "2. 正在進行的 plans 與 task 結構",
        "3. blockers、風險與卡點",
        "4. 建議下一步",
        "5. 如果需要，直接回答使用者對 task / subtask / plan 的操作問題",
        "Keep it concise and execution-oriented. Do not turn this into a management recap unless the user explicitly asks for one.",
        "If you need task governance detail or task-level evidence, use ZenOS MCP to fetch it and follow ZenOS task governance rules when reasoning about mutations.",
        "If the user asks to create or update work items, place them at the correct layer: plan vs task vs subtask, instead of flattening everything into tasks.",
        `Use this selected next step as the default recommendation unless the context clearly points to a better one: ${nextStep}.`,
        `If the root context is sparse, still explain the current state and give a concrete next step. Fallback context: ${fallback}`,
      ].join("\n"),
  };
}
