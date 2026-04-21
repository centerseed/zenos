"use client";

import React from "react";
import type { Task } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { Chip } from "@/components/zen/Chip";
import { extractFirstImage } from "./MarkdownRenderer";
import { getOverdueDays, getTaskRiskBadges } from "@/lib/task-risk";
import { Calendar, Bot, GitBranch, CornerUpRight } from "lucide-react";

interface TaskCardProps {
  task: Task;
  onSelect?: (task: Task) => void;
  entityNames?: Record<string, string>;
}

function dispatcherShort(value: string | null | undefined): string | null {
  if (!value) return null;
  if (value.startsWith("agent:")) return value.slice(6).toUpperCase();
  if (value === "human" || value.startsWith("human:")) return "HUMAN";
  return value;
}

function formatDate(date: Date | null): string {
  if (!date) return "";
  return date.toLocaleDateString("zh-TW", { month: "short", day: "numeric" });
}

function priorityTone(p: string): "accent" | "ocher" | "muted" {
  if (p === "critical" || p === "high") return "accent";
  if (p === "medium") return "ocher";
  return "muted";
}

function formatOrder(order: number | null | undefined): string {
  if (!Number.isFinite(order)) return "--";
  return String(order).padStart(2, "0");
}

export function TaskCard({ task, onSelect, entityNames = {} }: TaskCardProps) {
  const t = useInk("light");
  const { c, fontBody, fontMono, radius } = t;

  const thumbnail = task.description ? extractFirstImage(task.description) : null;
  const overdue = getOverdueDays(task) !== null;
  const dueDateStr = formatDate(task.dueDate);
  const riskBadges = getTaskRiskBadges(task);

  const isAgentCreated =
    task.creatorName?.includes("agent") || task.createdBy?.includes("agent");
  const mainName =
    task.assigneeName ||
    task.assignee ||
    task.creatorName ||
    task.createdBy ||
    "Unassigned";
  const displayName = mainName.replace(/^agent \(by (.*?)\)$/, "$1");

  const descPreview = task.description
    ? task.description
        .replace(/!\[.*?\]\(.*?\)/g, "")
        .replace(/\[([^\]]+)\]\(.*?\)/g, "$1")
        .replace(/[#*_~`>|]/g, "")
        .replace(/\n+/g, " ")
        .trim()
        .slice(0, 100)
    : null;

  // Overdue: 2px left vermillion border + vermSoft background tint
  const cardStyle: React.CSSProperties = {
    position: "relative",
    overflow: "hidden",
    cursor: "pointer",
    background: task.parentTaskId ? c.paperWarm : overdue ? c.vermSoft : c.surface,
    border: `1px solid ${c.inkHair}`,
    borderLeft: task.parentTaskId
      ? `3px solid ${c.vermLine}`
      : overdue
        ? `2px solid ${c.vermillion}`
        : `1px solid ${c.inkHair}`,
    borderRadius: radius,
    transition: "box-shadow 0.2s, border-color 0.2s",
  };

  return (
    <div
      style={cardStyle}
      onClick={() => onSelect?.(task)}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.borderColor = overdue ? c.vermillion : c.inkHairBold;
        el.style.boxShadow = "0 4px 20px rgba(58, 52, 44, 0.10)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.borderColor = overdue ? c.vermillion : c.inkHair;
        el.style.boxShadow = "none";
      }}
    >
      {/* Thumbnail */}
      {thumbnail && (
        <div
          style={{
            position: "relative",
            width: "100%",
            height: 112,
            overflow: "hidden",
            borderBottom: `1px solid ${c.inkHair}`,
          }}
        >
          <img
            src={thumbnail}
            alt=""
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: 0.85,
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(to top, rgba(20,18,16,0.40) 0%, transparent 60%)`,
            }}
          />
        </div>
      )}

      {/* Header */}
      <div style={{ padding: "10px 12px 6px" }}>
        {(task.planId || task.parentTaskId || task.planOrder !== null) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              flexWrap: "wrap",
              marginBottom: 8,
              fontFamily: fontMono,
              fontSize: 9,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: c.inkFaint,
            }}
          >
            {task.planId && (
              <span style={{ color: c.inkMuted }}>
                {entityNames[task.planId] ?? task.planId.slice(-6)}
              </span>
            )}
            {task.planOrder !== null && task.planOrder !== undefined && (
              <span style={{ color: c.vermillion }}>#{formatOrder(task.planOrder)}</span>
            )}
            {task.parentTaskId && (
              <span style={{ color: c.inkMuted }}>Subtask</span>
            )}
          </div>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 8,
          }}
        >
          {/* B3-01: title uses fontBody (sans), fw=500, fs=13, ls=0.02em */}
          <span
            style={{
              fontFamily: fontBody,
              fontSize: 13,
              fontWeight: 500,
              letterSpacing: "0.02em",
              lineHeight: 1.35,
              color: c.ink,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {task.title}
          </span>

          {/* B3-03: priority Chip tone mapped to accent/ocher/muted */}
          <Chip t={t} tone={priorityTone(task.priority)} dot style={{ flexShrink: 0 }}>
            {task.priority}
          </Chip>
        </div>

        {descPreview && (
          <p
            style={{
              fontFamily: fontBody,
              fontSize: 11,
              color: c.inkMuted,
              marginTop: 6,
              lineHeight: 1.55,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {descPreview}
          </p>
        )}
      </div>

      {/* Body chips */}
      <div style={{ padding: "0 12px 8px", display: "flex", flexDirection: "column", gap: 6 }}>
        {/* Dispatcher + Subtask chips — B3-03: tone="muted" (no multi-colour) */}
        {(task.dispatcher || task.parentTaskId) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {task.dispatcher && (
              <Chip
                t={t}
                tone={task.dispatcher.startsWith("human") ? "accent" : "muted"}
                dot
              >
                <GitBranch size={9} style={{ marginRight: 2 }} />
                {dispatcherShort(task.dispatcher)}
              </Chip>
            )}
            {task.parentTaskId && (
              <Chip t={t} tone="muted" dot>
                <CornerUpRight size={9} style={{ marginRight: 2 }} />
                SUB
              </Chip>
            )}
          </div>
        )}

        {/* Linked entity chips */}
        {task.linkedEntities.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {task.linkedEntities.slice(0, 2).map((id) => (
              <Chip key={id} t={t} tone="muted">
                {entityNames[id] ?? id.slice(0, 6)}
              </Chip>
            ))}
          </div>
        )}

        {/* Risk badges */}
        {riskBadges.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {riskBadges.map((badge) => (
              <Chip key={badge.kind} t={t} tone={overdue ? "accent" : "ocher"}>
                {badge.label}
              </Chip>
            ))}
          </div>
        )}

        {/* Footer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: `1px solid ${c.inkHair}`,
            paddingTop: 8,
            marginTop: 2,
          }}
        >
          {/* Avatar + name */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ position: "relative" }}>
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  background: c.vermSoft,
                  border: `1px solid ${c.vermLine}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 9,
                  fontWeight: 700,
                  color: c.vermillion,
                  fontFamily: fontBody,
                }}
              >
                {(displayName || "?")[0].toUpperCase()}
              </div>
              {isAgentCreated && (
                <div
                  style={{
                    position: "absolute",
                    bottom: -2,
                    right: -2,
                    background: c.surface,
                    borderRadius: "50%",
                    padding: 1,
                    border: `1px solid ${c.inkHair}`,
                  }}
                >
                  <Bot size={8} color={c.inkMuted} />
                </div>
              )}
            </div>
            <span
              style={{
                fontFamily: fontBody,
                fontSize: 10,
                fontWeight: 500,
                color: c.inkMuted,
                maxWidth: 80,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {displayName}
            </span>
          </div>

          {/* Due date + project */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {dueDateStr && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 3,
                  fontFamily: fontBody,
                  fontSize: 10,
                  fontWeight: 500,
                  color: overdue ? c.vermillion : c.inkMuted,
                }}
              >
                <Calendar size={10} />
                <span>{dueDateStr}</span>
              </div>
            )}

            {task.project && (
              <span
                style={{
                  fontFamily: fontMono,
                  fontSize: 9,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: c.inkFaint,
                  padding: "2px 6px",
                  border: `1px solid ${c.inkHair}`,
                  borderRadius: radius,
                }}
              >
                {task.project}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
