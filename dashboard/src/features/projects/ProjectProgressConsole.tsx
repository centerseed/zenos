"use client";

import { useEffect, useMemo, useState } from "react";
import { useInk } from "@/lib/zen-ink/tokens";
import { ProjectMilestoneStrip } from "@/features/projects/ProjectMilestoneStrip";
import { ProjectOpenWorkPanel } from "@/features/projects/ProjectOpenWorkPanel";
import { ProjectPlansOverview } from "@/features/projects/ProjectPlansOverview";
import { ProjectRecentProgress } from "@/features/projects/ProjectRecentProgress";
import { ProjectRecapRail } from "@/features/projects/ProjectRecapRail";
import {
  buildProjectContinuationPrompt,
  buildFallbackRecap,
  deriveProjectNextStepOptions,
} from "@/features/projects/projectPrompt";
import type { ProjectAgentPreset } from "@/features/projects/types";
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
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;
  const [internalRailOpen, setInternalRailOpen] = useState(false);
  const [preset, setPreset] = useState<ProjectAgentPreset>("claude_code");
  const [copiedState, setCopiedState] = useState<"idle" | "copied" | "error">("idle");
  const [latestRecap, setLatestRecap] = useState<string | null>(null);
  const nextStepOptions = useMemo(() => deriveProjectNextStepOptions(progress), [progress]);
  const [selectedNextStep, setSelectedNextStep] = useState(nextStepOptions[0]?.value || "");

  useEffect(() => {
    setSelectedNextStep(nextStepOptions[0]?.value || "");
  }, [nextStepOptions]);

  function handleRailOpenChange(next: boolean) {
    onRecapRailOpenChange?.(next);
    if (recapRailOpen === undefined) {
      setInternalRailOpen(next);
    }
  }

  async function handleCopyPrompt() {
    const prompt = buildProjectContinuationPrompt(progress, {
      preset,
      recap: latestRecap || buildFallbackRecap(progress),
      nextStep: selectedNextStep || nextStepOptions[0]?.value || `Review ${progress.project.name}`,
    });
    try {
      await navigator.clipboard.writeText(prompt);
      setCopiedState("copied");
    } catch {
      setCopiedState("error");
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
        </div>

        <div style={{ display: "grid", gap: 16 }}>
          <section
            data-testid="project-recap-toolbar"
            style={{
              background: c.paperWarm,
              border: `1px solid ${c.inkHair}`,
              padding: 18,
            }}
          >
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                marginBottom: 10,
              }}
            >
              Product Task Copilot
            </div>
            <div style={{ fontFamily: fontHead, fontSize: 18, color: c.ink, fontWeight: 500 }}>
              任務討論
            </div>

            <div style={{ display: "flex", gap: 8, margin: "10px 0 12px" }}>
              {(["claude_code", "codex"] as ProjectAgentPreset[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPreset(value)}
                  style={{
                    border: `1px solid ${preset === value ? c.vermLine : c.inkHair}`,
                    background: preset === value ? c.vermSoft : c.surface,
                    color: preset === value ? c.vermillion : c.ink,
                    padding: "6px 10px",
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  {value === "claude_code" ? "Claude Code" : "Codex"}
                </button>
              ))}
            </div>

            <label
              htmlFor="project-copilot-focus"
              style={{ display: "block", fontSize: 11, color: c.inkMuted, marginBottom: 6 }}
            >
              討論焦點
            </label>
            <select
              id="project-copilot-focus"
              aria-label="討論焦點"
              value={selectedNextStep}
              onChange={(event) => setSelectedNextStep(event.target.value)}
              style={{
                width: "100%",
                border: `1px solid ${c.inkHairBold}`,
                background: c.surface,
                color: c.ink,
                padding: "8px 10px",
                fontSize: 12,
                marginBottom: 12,
              }}
            >
              {nextStepOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => void handleCopyPrompt()}
                style={{
                  border: `1px solid ${c.vermLine}`,
                  background: c.vermSoft,
                  color: c.vermillion,
                  padding: "8px 12px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                複製 continuation prompt
              </button>
            </div>

            <div style={{ fontSize: 11, color: copiedState === "error" ? c.vermillion : c.inkMuted, marginTop: 10 }}>
              {copiedState === "copied"
                ? `已複製 ${preset === "claude_code" ? "Claude Code" : "Codex"} prompt`
                : copiedState === "error"
                  ? "複製失敗"
                  : "複製會帶目前 product context"}
            </div>
          </section>

          <ProjectRecapRail
            open={recapRailOpen ?? internalRailOpen}
            onOpenChange={handleRailOpenChange}
            progress={progress}
            preset={preset}
            nextStep={selectedNextStep}
            onRecapChange={setLatestRecap}
            onAssistantUpdate={onAssistantUpdate}
          />

          <ProjectRecentProgress items={progress.recent_progress} />
        </div>
      </div>
    </>
  );
}
