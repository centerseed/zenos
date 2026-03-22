"use client";

import type { Task, Entity, Partner } from "@/types";

interface ActivityTimelineProps {
  tasks: Task[];
  partners: Partner[];
  entities: Entity[];
}

function getActionLabel(task: Task): string {
  if (task.rejectionReason) return "rejected";
  switch (task.status) {
    case "done": return "completed";
    case "in_progress": return "in progress";
    case "blocked": return "blocked";
    case "review": return "submitted review";
    default: return "updated";
  }
}

function getActionIcon(task: Task): string {
  if (task.rejectionReason) return "\u274C";
  switch (task.status) {
    case "done": return "\u2705";
    case "in_progress": return "\uD83D\uDD04";
    case "blocked": return "\uD83D\uDD34";
    case "review": return "\uD83D\uDCCB";
    default: return "\uD83D\uDCDD";
  }
}

function relativeTime(date: Date): string {
  const now = Date.now();
  const diff = now - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function dateGroup(date: Date): string {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (d.getTime() >= today.getTime()) return "Today";
  if (d.getTime() >= yesterday.getTime()) return "Yesterday";
  return "Earlier";
}

export function ActivityTimeline({ tasks, partners, entities }: ActivityTimelineProps) {
  const sorted = [...tasks]
    .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
    .slice(0, 20);

  if (sorted.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Activity Timeline</h3>
        <p className="text-sm text-gray-400 text-center py-4">No recent activity</p>
      </div>
    );
  }

  const partnerMap = new Map(partners.map((p) => [p.id, p.displayName]));
  const entityMap = new Map(entities.map((e) => [e.id, e.name]));

  const groups: { label: string; items: Task[] }[] = [];
  let currentGroup = "";

  for (const task of sorted) {
    const group = dateGroup(task.updatedAt);
    if (group !== currentGroup) {
      currentGroup = group;
      groups.push({ label: group, items: [] });
    }
    groups[groups.length - 1].items.push(task);
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Activity Timeline</h3>
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.label}>
            <div className="text-xs font-semibold text-gray-400 uppercase mb-2">
              {group.label}
            </div>
            <div className="space-y-2 border-l-2 border-gray-100 ml-2 pl-4">
              {group.items.map((task) => {
                const assigneeName = task.assignee
                  ? partnerMap.get(task.assignee) ?? task.assignee
                  : "Unknown";
                const entityName =
                  task.linkedEntities.length > 0
                    ? entityMap.get(task.linkedEntities[0]) ?? null
                    : null;

                return (
                  <div key={task.id} className="flex items-start gap-2 text-sm">
                    <span className="text-xs text-gray-400 whitespace-nowrap mt-0.5">
                      {relativeTime(task.updatedAt)}
                    </span>
                    <span className="font-medium text-gray-700">
                      {assigneeName}
                    </span>
                    <span className="text-gray-500">
                      {getActionLabel(task)}
                    </span>
                    <span className="text-gray-900 font-medium truncate max-w-[200px]">
                      {task.title}
                    </span>
                    {entityName && (
                      <span className="text-xs text-gray-400">
                        → {entityName}
                      </span>
                    )}
                    <span>{getActionIcon(task)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
