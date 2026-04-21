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
  const railOpen = recapRailOpen ?? internalRailOpen;

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
            data-testid="project-recap-card"
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
              直接討論這個專案的 milestone、plan 與 task
            </div>
            <p style={{ fontSize: 12, color: c.inkMuted, margin: "8px 0 14px", lineHeight: 1.6 }}>
              直接詢問目前在哪個 milestone、哪個 task 卡住、subtask 怎麼拆、下一步先做什麼。需要丟去 Claude Code 或 Codex 再用 continuation prompt。
            </p>

            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
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

            <label style={{ display: "block", fontSize: 11, color: c.inkMuted, marginBottom: 6 }}>
              討論焦點
            </label>
            <select
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
                onClick={() => handleRailOpenChange(true)}
                style={{
                  border: `1px solid ${c.inkHairBold}`,
                  background: c.surface,
                  color: c.ink,
                  padding: "8px 12px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                開始任務討論
              </button>
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
                  : latestRecap
                    ? "已捕捉最新 task copilot 回覆，可直接複製 continuation prompt"
                    : "尚未開始 task 討論，複製時會使用 fallback context"}
            </div>

            <div
              style={{
                marginTop: 12,
                borderTop: `1px solid ${c.inkHair}`,
                paddingTop: 12,
                fontSize: 12,
                color: c.inkMuted,
                lineHeight: 1.7,
              }}
            >
              {latestRecap || `目前優先 milestone：${progress.milestones[0]?.name || "none"}。先從下列焦點切入：${selectedNextStep || nextStepOptions[0]?.value || buildFallbackRecap(progress)}`}
            </div>
          </section>

          <ProjectRecentProgress items={progress.recent_progress} />
        </div>
      </div>

      <ProjectRecapRail
        open={railOpen}
        onOpenChange={handleRailOpenChange}
        progress={progress}
        preset={preset}
        nextStep={selectedNextStep}
        onRecapChange={setLatestRecap}
        onAssistantUpdate={onAssistantUpdate}
      />
    </>
  );
}
