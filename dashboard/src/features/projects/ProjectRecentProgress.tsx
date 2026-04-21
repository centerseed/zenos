"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { ProjectRecentProgressItem } from "@/features/projects/types";

function formatShortDate(value: Date | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" });
}

export function ProjectRecentProgress({
  items,
}: {
  items: ProjectRecentProgressItem[];
}) {
  const t = useInk("light");
  const { c, fontMono } = t;

  return (
    <section
      data-testid="project-recent-progress"
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
        Recent Progress
      </div>
      {items.length === 0 ? (
        <div style={{ fontSize: 12, color: c.inkMuted }}>尚無近期推進摘要</div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {items.map((item) => (
            <div
              key={`${item.kind}-${item.id}`}
              style={{
                borderBottom: `1px solid ${c.inkHair}`,
                paddingBottom: 10,
              }}
            >
              <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{item.title}</div>
              <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{item.subtitle}</div>
              <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, marginTop: 4 }}>
                {formatShortDate(item.updated_at)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

