"use client";

import { useMemo, useState } from "react";
import { ProjectMilestoneStrip } from "@/features/projects/ProjectMilestoneStrip";
import { ProjectOpenWorkPanel } from "@/features/projects/ProjectOpenWorkPanel";
import { ProjectPlansOverview } from "@/features/projects/ProjectPlansOverview";
import { ProjectRecentProgress } from "@/features/projects/ProjectRecentProgress";
import { ProjectRecapRail } from "@/features/projects/ProjectRecapRail";
import { deriveProjectNextStepOptions } from "@/features/projects/projectPrompt";
import type { TaskHubFocus } from "@/features/tasks/taskHub";
import type { ProjectProgressResponse } from "@/lib/api";

export function ProjectProgressConsole({
  progress,
  focus,
  onOpenTasks,
  recapRailOpen,
  onRecapRailOpenChange,
  onAssistantUpdate,
}: {
  progress: ProjectProgressResponse;
  focus?: TaskHubFocus | null;
  onOpenTasks: () => void;
  recapRailOpen?: boolean;
  onRecapRailOpenChange?: (next: boolean) => void;
  onAssistantUpdate?: (recap: string) => void;
}) {
  const [internalRailOpen, setInternalRailOpen] = useState(false);
  const nextStepOptions = useMemo(() => deriveProjectNextStepOptions(progress), [progress]);
  const selectedNextStep = nextStepOptions[0]?.value || `Review ${progress.project.name}`;
  const focusedMilestoneId = focus?.startsWith("milestone:") ? focus.slice("milestone:".length) : null;
  const focusedPlanId = focus?.startsWith("plan:") ? focus.slice("plan:".length) : null;

  function handleRailOpenChange(next: boolean) {
    onRecapRailOpenChange?.(next);
    if (recapRailOpen === undefined) {
      setInternalRailOpen(next);
    }
  }

  return (
    <>
      <div
        data-testid="project-progress-console"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(320px, 0.8fr)",
          gap: 20,
        }}
      >
        <div style={{ display: "grid", gap: 16 }}>
          <ProjectMilestoneStrip milestones={progress.milestones} focusedMilestoneId={focusedMilestoneId} />
          <ProjectPlansOverview
            plans={progress.active_plans}
            milestones={progress.milestones}
            groups={progress.open_work_groups}
            focusedPlanId={focusedPlanId}
            focusedMilestoneId={focusedMilestoneId}
          />
          <ProjectOpenWorkPanel groups={progress.open_work_groups} onOpenTasks={onOpenTasks} />
          <ProjectRecentProgress items={progress.recent_progress} />
        </div>

        <div
          data-testid="project-recap-rail-column"
          style={{
            display: "grid",
            gap: 16,
            position: "sticky",
            top: 20,
            alignSelf: "start",
            maxHeight: "calc(100vh - 40px)",
          }}
        >
          <ProjectRecapRail
            open={recapRailOpen ?? internalRailOpen}
            onOpenChange={handleRailOpenChange}
            progress={progress}
            preset="claude_code"
            nextStep={selectedNextStep}
            onRecapChange={() => {}}
            onAssistantUpdate={onAssistantUpdate}
          />
        </div>
      </div>
    </>
  );
}
