"use client";

import Link from "next/link";
import type { Entity } from "@/types";

interface ProjectCardProps {
  entity: Entity;
  moduleCount: number;
}

const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  paused: "bg-yellow-100 text-yellow-700",
  planned: "bg-blue-100 text-blue-700",
  completed: "bg-gray-100 text-gray-500",
};

export function ProjectCard({ entity, moduleCount }: ProjectCardProps) {
  return (
    <Link href={`/projects?id=${entity.id}`}>
      <div className="border border-gray-200 rounded-lg p-6 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer bg-white">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-lg font-semibold text-gray-900">{entity.name}</h3>
          <span
            className={`text-xs px-2 py-1 rounded-full ${statusColors[entity.status] ?? "bg-gray-100 text-gray-500"}`}
          >
            {entity.status}
          </span>
        </div>
        <p className="text-gray-600 text-sm mb-4 line-clamp-2">
          {entity.summary}
        </p>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>{moduleCount} modules</span>
          <span>
            Updated{" "}
            {entity.updatedAt.toLocaleDateString("zh-TW")}
          </span>
        </div>
      </div>
    </Link>
  );
}
