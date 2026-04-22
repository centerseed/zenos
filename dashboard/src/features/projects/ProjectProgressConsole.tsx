"use client";

import { useMemo, useState } from "react";
import { ProjectMilestoneStrip } from "@/features/projects/ProjectMilestoneStrip";
import { ProjectOpenWorkPanel } from "@/features/projects/ProjectOpenWorkPanel";
import { ProjectPlansOverview } from "@/features/projects/ProjectPlansOverview";
import { ProjectRecentProgress } from "@/features/projects/ProjectRecentProgress";
import { ProjectRecapRail } from "@/features/projects/ProjectRecapRail";
import { deriveProjectNextStepOptions } from "@/features/projects/projectPrompt";
import type { ProjectProgressResponse } from "@/lib/api";

export function ProjectProgressConsole({
  progress,
  onOpenTasks,
  recapRailOpen,
  onRecapRailOpenChange,
  onAssistantUpdate,
}: {
  progress: ProjectProgressResponse;
  onOpenTasks: () => void;
  recapRailOpen?: boolean;
  onRecapRailOpenChange?: (next: boolean) => void;
  onAssistantUpdate?: (recap: string) => void;
}) {
  const [internalRailOpen, setInternalRailOpen] = useState(false);
  const nextStepOptions = useMemo(() => deriveProjectNextStepOptions(progress), [progress]);
  const selectedNextStep = nextStepOptions[0]?.value || `Review ${progress.project.name}`;

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
          <ProjectMilestoneStrip milestones={progress.milestones} />
          <ProjectPlansOverview
            plans={progress.active_plans}
            milestones={progress.milestones}
            groups={progress.open_work_groups}
          />
          <ProjectOpenWorkPanel groups={progress.open_work_groups} onOpenTasks={onOpenTasks} />
          <ProjectRecentProgress items={progress.recent_progress} />
        </div>

        <div style={{ display: "grid", gap: 16 }}>
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
