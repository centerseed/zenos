"use client";

import type { Task } from "@/types";

const CLOSED_STATUSES = new Set(["done", "cancelled", "archived"]);
const DAY_MS = 24 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

export function isClosedTask(task: Task): boolean {
  return CLOSED_STATUSES.has(task.status);
}

export function getOverdueDays(task: Task, now = new Date()): number | null {
  if (!task.dueDate || isClosedTask(task)) return null;
  const diff = now.getTime() - task.dueDate.getTime();
  if (diff <= 0) return null;
  return Math.max(1, Math.ceil(diff / DAY_MS));
}

export function getUpcomingDueDays(task: Task, now = new Date()): number | null {
  if (!task.dueDate || isClosedTask(task)) return null;
  const diff = task.dueDate.getTime() - now.getTime();
  if (diff <= 0) return null;
  const days = Math.ceil(diff / DAY_MS);
  return days <= 3 ? days : null;
}

export function getIdleTodoHours(task: Task, now = new Date()): number | null {
  if (task.status !== "todo" || !task.assignee || isClosedTask(task)) return null;
  const diff = now.getTime() - task.updatedAt.getTime();
  if (diff <= 48 * HOUR_MS) return null;
  return Math.floor(diff / HOUR_MS);
}

export interface TaskRiskBadge {
  kind: "overdue" | "upcoming" | "idle";
  label: string;
  className: string;
}

export function getTaskRiskBadges(task: Task, now = new Date()): TaskRiskBadge[] {
  const overdueDays = getOverdueDays(task, now);
  const upcomingDays = overdueDays === null ? getUpcomingDueDays(task, now) : null;
  const idleHours = getIdleTodoHours(task, now);

  const badges: TaskRiskBadge[] = [];

  if (overdueDays !== null) {
    badges.push({
      kind: "overdue",
      label: `逾期 ${overdueDays} 天`,
      className: "bg-red-500/15 text-red-300 border-red-500/30",
    });
  } else if (upcomingDays !== null) {
    badges.push({
      kind: "upcoming",
      label: `${upcomingDays} 天後到期`,
      className: "bg-orange-500/15 text-orange-300 border-orange-500/30",
    });
  }

  if (idleHours !== null) {
    badges.push({
      kind: "idle",
      label: `未開始 ${idleHours}h`,
      className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
    });
  }

  return badges;
}

export function isMine(task: Task, partnerId: string): boolean {
  return (task.assignee || "").toLowerCase() === partnerId.toLowerCase();
}

export function isCreatedByMe(task: Task, partnerId: string): boolean {
  const direct = (task.createdBy || "").toLowerCase() === partnerId.toLowerCase();
  const actorPartnerId = typeof task.sourceMetadata?.actor_partner_id === "string"
    ? task.sourceMetadata.actor_partner_id.toLowerCase()
    : "";
  return direct || actorPartnerId === partnerId.toLowerCase();
}
