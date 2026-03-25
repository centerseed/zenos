"use client";

import type { Task, Entity, Partner } from "@/types";

interface PeopleMatrixProps {
  tasks: Task[];
  entities: Entity[];
  partners: Partner[];
}

type StatusRank = "blocked" | "in_progress" | "review" | "todo" | "backlog" | "done";

const STATUS_PRIORITY: StatusRank[] = [
  "blocked",
  "in_progress",
  "review",
  "todo",
  "backlog",
  "done",
];

const STATUS_LABELS: Record<StatusRank, string> = {
  blocked: "BLOCKED",
  in_progress: "WORKING",
  review: "REVIEW",
  todo: "TODO",
  backlog: "BACKLOG",
  done: "DONE",
};

const STATUS_COLORS: Record<StatusRank, string> = {
  blocked: "bg-red-900/50 text-red-400",
  in_progress: "bg-yellow-900/50 text-yellow-400",
  review: "bg-purple-900/50 text-purple-400",
  todo: "bg-blue-900/50 text-blue-400",
  backlog: "bg-secondary text-muted-foreground",
  done: "bg-green-900/50 text-green-400",
};

function getHighestStatus(cellTasks: Task[]): StatusRank | null {
  if (cellTasks.length === 0) return null;
  const statuses = new Set(cellTasks.map((t) => t.status));
  for (const s of STATUS_PRIORITY) {
    if (statuses.has(s)) return s;
  }
  return null;
}

function hasOverdue(cellTasks: Task[]): boolean {
  const now = Date.now();
  return cellTasks.some(
    (t) =>
      t.dueDate !== null &&
      t.dueDate.getTime() < now &&
      !["done", "cancelled", "archived"].includes(t.status)
  );
}

export function PeopleMatrix({ tasks, entities, partners }: PeopleMatrixProps) {
  const assignees = Array.from(
    new Set(tasks.map((t) => t.assignee).filter((a): a is string => a !== null))
  ).sort();

  if (assignees.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-6">
        <h3 className="text-sm font-semibold text-white mb-4">People x Projects</h3>
        <p className="text-sm text-muted-foreground text-center py-4">No tasks assigned yet</p>
      </div>
    );
  }

  const partnerMap = new Map(partners.map((p) => [p.id, p.displayName]));

  function displayName(assignee: string): string {
    return partnerMap.get(assignee) ?? assignee;
  }

  return (
    <div className="bg-card rounded-lg border border-border p-6">
      <h3 className="text-sm font-semibold text-white mb-4">People x Projects</h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-left text-xs font-medium text-muted-foreground pb-3 pr-4">
                Person
              </th>
              {entities.map((e) => (
                <th
                  key={e.id}
                  className="text-left text-xs font-medium text-muted-foreground pb-3 px-3"
                >
                  {e.name}
                </th>
              ))}
              <th className="text-right text-xs font-medium text-muted-foreground pb-3 pl-4">
                Summary
              </th>
            </tr>
          </thead>
          <tbody>
            {assignees.map((assignee) => {
              const personTasks = tasks.filter((t) => t.assignee === assignee);
              const doneCount = personTasks.filter((t) => t.status === "done").length;
              const remaining = personTasks.filter(
                (t) => !["done", "cancelled", "archived"].includes(t.status)
              ).length;

              return (
                <tr key={assignee} className="border-t border-border">
                  <td className="py-3 pr-4 text-sm font-medium text-foreground whitespace-nowrap">
                    {displayName(assignee)}
                  </td>
                  {entities.map((entity) => {
                    const cellTasks = tasks.filter(
                      (t) =>
                        t.assignee === assignee &&
                        t.linkedEntities.includes(entity.id)
                    );
                    const activeCellTasks = cellTasks.filter(
                      (t) => !["done", "cancelled", "archived"].includes(t.status)
                    );
                    const activeCount = activeCellTasks.length;

                    if (cellTasks.length === 0) {
                      return (
                        <td key={entity.id} className="py-3 px-3">
                          <span className="text-secondary">-</span>
                        </td>
                      );
                    }

                    const highestStatus = getHighestStatus(cellTasks);
                    const isBlocked = cellTasks.some((t) => t.status === "blocked");
                    const isOverdue = hasOverdue(cellTasks);
                    const allDone = cellTasks.every(
                      (t) => t.status === "done" || t.status === "cancelled" || t.status === "archived"
                    );

                    let cellBg = "bg-card";
                    let cellBorder = "border border-border";
                    if (isBlocked) {
                      cellBg = "bg-red-900/20";
                      cellBorder = "border border-red-800";
                    } else if (isOverdue) {
                      cellBorder = "border-2 border-orange-600";
                    } else if (allDone) {
                      cellBg = "bg-green-900/20";
                      cellBorder = "border border-green-800";
                    }

                    return (
                      <td key={entity.id} className="py-3 px-3">
                        <div
                          className={`rounded-lg p-2 ${cellBg} ${cellBorder}`}
                        >
                          <div className="flex items-center gap-1 mb-1">
                            {Array.from({ length: Math.min(activeCount, 5) }).map((_, i) => (
                              <span
                                key={i}
                                className="inline-block w-2 h-2 rounded-full bg-muted-foreground"
                              />
                            ))}
                            {activeCount > 5 && (
                              <span className="text-xs text-muted-foreground">+{activeCount - 5}</span>
                            )}
                          </div>
                          {highestStatus && (
                            <span
                              className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[highestStatus]}`}
                            >
                              {STATUS_LABELS[highestStatus]}
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                  <td className="py-3 pl-4 text-right text-xs text-muted-foreground whitespace-nowrap">
                    done {doneCount} / left {remaining}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
