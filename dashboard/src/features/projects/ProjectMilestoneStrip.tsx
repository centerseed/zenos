"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { ProjectProgressMilestone } from "@/features/projects/types";

export function ProjectMilestoneStrip({
  milestones,
  focusedMilestoneId,
}: {
  milestones: ProjectProgressMilestone[];
  focusedMilestoneId?: string | null;
}) {
  const t = useInk("light");
  const { c, fontMono } = t;

  return (
    <section
      data-testid="project-milestone-strip"
      style={{
        background: c.surface,
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
          marginBottom: 12,
        }}
      >
        Milestones / 階段
      </div>
      {milestones.length === 0 ? (
        <div style={{ fontSize: 12, color: c.inkMuted }}>目前沒有 milestone 訊號</div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {milestones.map((milestone) => (
            <div
              key={milestone.id}
              style={{
                border: `1px solid ${milestone.id === focusedMilestoneId ? c.vermillion : c.vermLine}`,
                background: milestone.id === focusedMilestoneId ? c.surface : c.vermSoft,
                padding: "8px 12px",
              }}
            >
              <div style={{ fontSize: 12, color: c.ink, fontWeight: 500 }}>
                {milestone.name}
                {milestone.id === focusedMilestoneId ? " · current focus" : ""}
              </div>
              <div style={{ fontSize: 10, color: c.inkMuted, marginTop: 3 }}>{milestone.open_count} open item(s)</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
