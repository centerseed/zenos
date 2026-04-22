"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { TaskHubSnapshot } from "@/features/tasks/taskHub";

export function TaskHubRecap({
  snapshot,
  onOpenBoard,
}: {
  snapshot: TaskHubSnapshot;
  onOpenBoard: () => void;
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;
  const summaryItems = [
    { label: "Products", value: String(snapshot.summary.productCount), sub: "portfolio" },
    { label: "Current Milestones", value: String(snapshot.summary.activeMilestoneCount), sub: "in motion" },
    { label: "Active Plans", value: String(snapshot.summary.activePlanCount), sub: "still executing" },
    {
      label: "Portfolio Risk",
      value: String(snapshot.summary.blockedPlanCount + snapshot.summary.overdueWorkCount),
      sub: `${snapshot.summary.blockedPlanCount} blocked plan · ${snapshot.summary.overdueWorkCount} overdue`,
    },
  ];

  return (
    <section
      data-testid="task-hub-recap"
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: 20,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 18,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: fontMono,
              fontSize: 10,
              color: c.inkFaint,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            Task Hub / Portfolio Recap
          </div>
          <h2
            style={{
              margin: 0,
              fontFamily: fontHead,
              fontSize: 24,
              fontWeight: 500,
              color: c.ink,
              letterSpacing: "0.03em",
            }}
          >
            先看全局，再決定往哪個產品下鑽
          </h2>
          <p
            style={{
              margin: "10px 0 0",
              maxWidth: 720,
              fontSize: 13,
              lineHeight: 1.7,
              color: c.inkMuted,
            }}
          >
            這一屏只回答哪個 product、milestone、plan 現在最值得往下看。真正的 task execution board 往下沉到第二層。
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenBoard}
          style={{
            border: `1px solid ${c.inkHairBold}`,
            background: c.paperWarm,
            padding: "10px 14px",
            fontSize: 12,
            color: c.ink,
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          查看執行板
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 1,
          background: c.inkHair,
          border: `1px solid ${c.inkHair}`,
        }}
      >
        {summaryItems.map((item) => (
          <div key={item.label} style={{ background: c.surface, padding: "14px 16px" }}>
            <div
              style={{
                fontFamily: fontMono,
                fontSize: 10,
                color: c.inkFaint,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              {item.label}
            </div>
            <div
              style={{
                fontFamily: fontHead,
                fontSize: 28,
                color: c.ink,
                fontWeight: 500,
              }}
            >
              {item.value}
            </div>
            <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 3 }}>{item.sub}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
