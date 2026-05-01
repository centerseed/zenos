"use client";

import { useInk } from "@/lib/zen-ink/tokens";
import type { TaskHubFocus, TaskHubSnapshot } from "@/features/tasks/taskHub";

function toneStyles(riskLevel: "critical" | "warning" | "healthy", colors: ReturnType<typeof useInk>["c"]) {
  if (riskLevel === "critical") {
    return {
      border: colors.vermLine,
      background: colors.vermSoft,
      label: colors.vermillion,
      text: "Risk",
    };
  }
  if (riskLevel === "warning") {
    return {
      border: "rgba(180, 132, 50, 0.28)",
      background: "rgba(180, 132, 50, 0.10)",
      label: colors.ocher,
      text: "Watch",
    };
  }
  return {
    border: colors.inkHairBold,
    background: colors.surface,
    label: colors.jade,
    text: "Healthy",
  };
}

export function ProductHealthList({
  snapshot,
  onOpenProduct,
  onOpenFocus,
}: {
  snapshot: TaskHubSnapshot;
  onOpenProduct: (productId: string) => void;
  onOpenFocus: (productId: string, focus: TaskHubFocus) => void;
}) {
  const t = useInk("light");
  const { c, fontHead, fontMono } = t;

  const visibleProducts = snapshot.products.filter((product) => product.openTaskCount > 0);
  if (visibleProducts.length === 0) return null;

  return (
    <section
      data-testid="product-health-list"
      style={{
        background: c.surface,
        border: `1px solid ${c.inkHair}`,
        padding: 20,
      }}
    >
      <div
        style={{
          fontFamily: fontMono,
          fontSize: 10,
          color: c.inkFaint,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          marginBottom: 14,
        }}
      >
        Products by Health
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {visibleProducts.map((product) => {
          const tone = toneStyles(product.riskLevel, c);
          const primaryPlan = product.plans[0] ?? null;
          const primaryMilestone = product.currentMilestone;

          return (
            <div
              key={product.productId}
              data-testid="product-health-card"
              style={{
                border: `1px solid ${tone.border}`,
                background: tone.background,
                padding: 16,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: fontMono,
                        fontSize: 10,
                        color: tone.label,
                        letterSpacing: "0.16em",
                        textTransform: "uppercase",
                      }}
                    >
                      {tone.text}
                    </span>
                    <span style={{ fontSize: 11, color: c.inkMuted }}>
                      {product.blockedCount} blocked · {product.reviewCount} review · {product.overdueCount} overdue
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onOpenProduct(product.productId)}
                    style={{
                      background: "transparent",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <div
                      style={{
                        fontFamily: fontHead,
                        fontSize: 20,
                        fontWeight: 500,
                        color: c.ink,
                        lineHeight: 1.35,
                      }}
                    >
                      {product.productName}
                    </div>
                  </button>
                  <div style={{ fontSize: 12, color: c.inkMuted, lineHeight: 1.6, marginTop: 6 }}>
                    {product.productSummary || "目前沒有摘要。"}
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gap: 6,
                    minWidth: 180,
                    justifyItems: "end",
                  }}
                >
                  <Metric label="Open" value={product.openTaskCount} />
                  <Metric label="Plans" value={product.activePlanCount} />
                  <Metric label="Updated" value={product.lastUpdatedAt ? product.lastUpdatedAt.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" }) : "—"} />
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  marginTop: 14,
                }}
              >
                {primaryMilestone ? (
                  <button
                    type="button"
                    onClick={() => onOpenFocus(product.productId, `milestone:${primaryMilestone.id}`)}
                    style={focusButtonStyle(c, true)}
                  >
                    Milestone · {primaryMilestone.name}
                  </button>
                ) : (
                  <span style={focusLabelStyle(c)}>Milestone · 未設定</span>
                )}
                {primaryPlan ? (
                  <button
                    type="button"
                    onClick={() => onOpenFocus(product.productId, `plan:${primaryPlan.id}`)}
                    style={focusButtonStyle(c, false)}
                  >
                    Plan · {primaryPlan.goal}
                  </button>
                ) : (
                  <span style={focusLabelStyle(c)}>Plan · 未設定</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
      <span
        style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 10,
          letterSpacing: "0.14em",
          color: "var(--zen-ink-faint, #8e8679)",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: 13, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function focusButtonStyle(colors: ReturnType<typeof useInk>["c"], accent: boolean) {
  return {
    border: `1px solid ${accent ? colors.vermLine : colors.inkHairBold}`,
    background: accent ? colors.vermSoft : colors.paperWarm,
    color: colors.ink,
    padding: "7px 10px",
    cursor: "pointer",
    fontSize: 11,
    textAlign: "left" as const,
  };
}

function focusLabelStyle(colors: ReturnType<typeof useInk>["c"]) {
  return {
    border: `1px solid ${colors.inkHair}`,
    background: colors.surface,
    color: colors.inkMuted,
    padding: "7px 10px",
    fontSize: 11,
  };
}
