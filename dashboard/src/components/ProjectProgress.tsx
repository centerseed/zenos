"use client";

import type { Task, Entity } from "@/types";

interface ProjectProgressProps {
  tasks: Task[];
  entities: Entity[];
}

interface ProjectStat {
  entity: Entity;
  total: number;
  done: number;
  percent: number;
}

export function ProjectProgress({ tasks, entities }: ProjectProgressProps) {
  if (entities.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Projects Progress</h3>
        <p className="text-sm text-gray-400 text-center py-4">No projects yet</p>
      </div>
    );
  }

  const stats: ProjectStat[] = entities
    .map((entity) => {
      const linked = tasks.filter((t) =>
        t.linkedEntities.includes(entity.id)
      );
      const total = linked.length;
      const done = linked.filter((t) => t.status === "done").length;
      const percent = total === 0 ? 0 : Math.round((done / total) * 100);
      return { entity, total, done, percent };
    })
    .sort((a, b) => b.percent - a.percent);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Projects Progress</h3>
      <div className="space-y-4">
        {stats.map(({ entity, total, done, percent }) => {
          let barColor = "bg-red-500";
          if (percent > 70) barColor = "bg-green-500";
          else if (percent >= 30) barColor = "bg-yellow-500";

          return (
            <div key={entity.id}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-700">
                  {entity.name}
                </span>
                <span className="text-xs text-gray-500">
                  {done}/{total}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className={`${barColor} rounded-full h-2 transition-all`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-gray-600 w-10 text-right">
                  {percent}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
