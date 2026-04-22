"use client";

import React from "react";
import type { Task } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { AlertTriangle, Clock3, Forward, Layers } from "lucide-react";
import { Btn } from "./zen/Btn";

interface TaskDetailOverviewProps {
  task: Task;
  ownerField: React.ReactNode;
  dueField: React.ReactNode;
  projectField: React.ReactNode;
  priorityField: React.ReactNode;
  nextActionLabel: string;
  blockedReason?: string | null;
  isOverdue: boolean;
  structureSummary?: string | null;
  onOpenStructure?: () => void;
  description: React.ReactNode;
  acceptanceCriteria?: React.ReactNode;
  result?: React.ReactNode;
  attachments?: React.ReactNode;
}

function sectionLabel(label: string, color: string) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <div style={{ width: 3, height: 16, borderRadius: 999, background: color, flexShrink: 0 }} />
      <span
        style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.16em",
          color: "inherit",
        }}
      >
        {label}
      </span>
    </div>
  );
}

export function TaskDetailOverview({
  task,
  ownerField,
  dueField,
  projectField,
  priorityField,
  nextActionLabel,
  blockedReason,
  isOverdue,
  structureSummary,
  onOpenStructure,
  description,
  acceptanceCriteria,
  result,
  attachments,
}: TaskDetailOverviewProps) {
  const t = useInk("light");
  const { c } = t;
  const riskItems = [
    blockedReason ? { label: "Blocked", tone: c.vermillion, detail: blockedReason, icon: AlertTriangle } : null,
    isOverdue ? { label: "Overdue", tone: c.ocher, detail: "已超過 due date，應優先處理。", icon: Clock3 } : null,
  ].filter(Boolean) as Array<{ label: string; tone: string; detail: string; icon: React.ComponentType<{ style?: React.CSSProperties }> }>;

  return (
    <div data-testid="task-detail-overview" style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      <section
        style={{
          background: c.paperWarm,
          border: `1px solid ${c.inkHair}`,
          borderRadius: t.radius,
          padding: 18,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 14,
          }}
        >
          <SummaryBlock label="Owner" value={ownerField} />
          <SummaryBlock label="Due" value={dueField} />
          <SummaryBlock label="Project" value={projectField} />
          <SummaryBlock label="Priority" value={priorityField} />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: riskItems.length > 0 ? "1.1fr 1fr" : "1fr",
            gap: 14,
          }}
        >
          <div
            style={{
              background: c.surface,
              border: `1px solid ${c.inkHair}`,
              borderRadius: t.radius,
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <span
              style={{
                fontFamily: t.fontMono,
                fontSize: 10,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.14em",
                color: c.inkFaint,
              }}
            >
              Next Action
            </span>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              <Forward style={{ width: 14, height: 14, color: c.vermillion, marginTop: 3, flexShrink: 0 }} />
              <p
                style={{
                  margin: 0,
                  fontFamily: t.fontBody,
                  fontSize: 14,
                  fontWeight: 600,
                  color: c.ink,
                  lineHeight: 1.55,
                }}
              >
                {nextActionLabel}
              </p>
            </div>
            <p
              style={{
                margin: 0,
                fontFamily: t.fontBody,
                fontSize: 12,
                color: c.inkMuted,
                lineHeight: 1.6,
              }}
            >
              先完成這一步，再處理 handoff / review / richer context。
            </p>
          </div>

          {riskItems.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {riskItems.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.label}
                    style={{
                      background: c.surface,
                      border: `1px solid ${item.tone === c.vermillion ? c.vermLine : c.inkHair}`,
                      borderRadius: t.radius,
                      padding: 14,
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Icon style={{ width: 13, height: 13, color: item.tone }} />
                      <span
                        style={{
                          fontFamily: t.fontMono,
                          fontSize: 10,
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.14em",
                          color: item.tone,
                        }}
                      >
                        {item.label}
                      </span>
                    </div>
                    <p style={{ margin: 0, fontFamily: t.fontBody, fontSize: 12, color: c.inkMuted, lineHeight: 1.6 }}>
                      {item.detail}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {(structureSummary || onOpenStructure) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "12px 14px",
              borderRadius: t.radius,
              border: `1px solid ${c.inkHair}`,
              background: c.surface,
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, minWidth: 0 }}>
              <Layers style={{ width: 14, height: 14, color: c.inkMuted, marginTop: 2, flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontFamily: t.fontMono,
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.14em",
                    color: c.inkFaint,
                    marginBottom: 4,
                  }}
                >
                  Structure Summary
                </div>
                <p
                  style={{
                    margin: 0,
                    fontFamily: t.fontBody,
                    fontSize: 12,
                    color: c.inkMuted,
                    lineHeight: 1.55,
                  }}
                >
                  {structureSummary || "目前沒有 plan / parent / subtask 結構資訊。"}
                </p>
              </div>
            </div>
            {onOpenStructure && (
              <Btn t={t} variant="ghost" size="sm" onClick={onOpenStructure}>
                查看 Structure
              </Btn>
            )}
          </div>
        )}
      </section>

      <section>
        {sectionLabel("Instruction & Logic", c.vermillion)}
        {description}
      </section>

      {acceptanceCriteria && <section>{sectionLabel("Success Criteria", c.vermillion)}{acceptanceCriteria}</section>}
      {result && <section>{sectionLabel("Outcome", c.jade)}{result}</section>}
      {attachments && <section>{attachments}</section>}

      {task.contextSummary && (
        <section
          style={{
            padding: 14,
            borderRadius: t.radius,
            background: c.surface,
            border: `1px solid ${c.inkHair}`,
          }}
        >
          <div
            style={{
              fontFamily: t.fontMono,
              fontSize: 10,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.14em",
              color: c.inkFaint,
              marginBottom: 6,
            }}
          >
            Context Summary
          </div>
          <p style={{ margin: 0, fontFamily: t.fontBody, fontSize: 12, color: c.inkMuted, lineHeight: 1.6 }}>
            {task.contextSummary}
          </p>
        </section>
      )}
    </div>
  );
}

function SummaryBlock({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span
        style={{
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color: "var(--zen-ink-faint, #8f867b)",
        }}
      >
        {label}
      </span>
      <div style={{ fontSize: 13, lineHeight: 1.5 }}>{value}</div>
    </div>
  );
}
