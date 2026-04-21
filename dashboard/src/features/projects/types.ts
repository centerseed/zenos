"use client";

export type {
  ProjectProgressMilestone,
  ProjectProgressOpenWorkGroup,
  ProjectProgressPlanSummary,
  ProjectProgressResponse,
  ProjectProgressTaskSummary,
  ProjectRecentProgressItem,
} from "@/lib/api";

export type ProjectAgentPreset = "claude_code" | "codex";

export interface ProjectNextStepOption {
  value: string;
  label: string;
}

