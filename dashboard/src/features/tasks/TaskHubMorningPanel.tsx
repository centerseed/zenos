"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { TaskHubSnapshot } from "@/features/tasks/taskHub";

export function TaskHubMorningPanel({
  snapshot,
  mySummary,
  filterSummary,
}: {
  snapshot: TaskHubSnapshot;
  mySummary: {
    openCount: number;
    reviewCount: number;
    blockedCount: number;
    overdueCount: number;
  };
  filterSummary: string[];
}) {
  const t = useInk("light");
  const { c, fontMono, fontHead } = t;

  return (
    <section
      data-testid="task-hub-morning-panel"
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: 20,
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.1fr) minmax(260px, 0.9fr)",
          gap: 18,
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
              marginBottom: 10,
            }}
          >
            Morning Brief / Recent Changes
          </div>
          {snapshot.recentChanges.length === 0 ? (
            <div style={{ fontSize: 12, color: c.inkMuted }}>目前沒有新的跨產品變化。</div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {snapshot.recentChanges.map((item) => (
                <div
                  key={item.id}
                  style={{
                    border: `1px solid ${c.inkHair}`,
                    background: c.paper,
                    padding: "10px 12px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: c.ink }}>{item.title}</div>
                      <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 4 }}>
                        {item.productName} · {item.subtitle}
                      </div>
                    </div>
                    <div
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: c.inkFaint,
                        letterSpacing: "0.12em",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.updatedAt
                        ? item.updatedAt.toLocaleDateString("zh-TW", {
                            month: "2-digit",
                            day: "2-digit",
                          })
                        : "—"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: "grid", gap: 14 }}>
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
              Personal Risk Summary
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
              {[
                { label: "Open", value: mySummary.openCount },
                { label: "Review", value: mySummary.reviewCount },
                { label: "Blocked", value: mySummary.blockedCount },
                { label: "Overdue", value: mySummary.overdueCount },
              ].map((item) => (
                <div key={item.label} style={{ background: c.surface, padding: "12px 10px" }}>
                  <div
                    style={{
                      fontFamily: fontMono,
                      fontSize: 9,
                      color: c.inkFaint,
                      letterSpacing: "0.14em",
                      textTransform: "uppercase",
                      marginBottom: 6,
                    }}
                  >
                    {item.label}
                  </div>
                  <div style={{ fontFamily: fontHead, fontSize: 22, color: c.ink }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>

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
              Filter Snapshot
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {filterSummary.length > 0 ? (
                filterSummary.map((item) => (
                  <span
                    key={item}
                    style={{
                      border: `1px solid ${c.inkHairBold}`,
                      background: c.paperWarm,
                      color: c.ink,
                      padding: "6px 10px",
                      fontSize: 11,
                    }}
                  >
                    {item}
                  </span>
                ))
              ) : (
                <span
                  style={{
                    border: `1px solid ${c.inkHair}`,
                    background: c.surface,
                    color: c.inkMuted,
                    padding: "6px 10px",
                    fontSize: 11,
                  }}
                >
                  All tasks · All products · All dispatchers
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
