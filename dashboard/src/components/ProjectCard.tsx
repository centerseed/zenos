"use client";

import Link from "next/link";
import type { Entity } from "@/types";

interface ProjectCardProps {
  entity: Entity;
  moduleCount: number;
}

const statusColors: Record<string, string> = {
  active: "bg-green-900/50 text-green-400",
  paused: "bg-yellow-900/50 text-yellow-400",
  planned: "bg-blue-900/50 text-blue-400",
  completed: "bg-[#1F1F23] text-[#71717A]",
};

export function ProjectCard({ entity, moduleCount }: ProjectCardProps) {
  return (
    <Link href={`/projects?id=${entity.id}`}>
      <div className="border border-[#1F1F23] rounded-lg p-6 hover:border-blue-800 hover:shadow-sm transition-all cursor-pointer bg-[#111113]">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-lg font-semibold text-white">{entity.name}</h3>
          <span
            className={`text-xs px-2 py-1 rounded-full ${statusColors[entity.status] ?? "bg-[#1F1F23] text-[#71717A]"}`}
          >
            {entity.status}
          </span>
        </div>
        <p className="text-[#71717A] text-sm mb-4 line-clamp-2">
          {entity.summary}
        </p>
        <div className="flex items-center gap-4 text-xs text-[#71717A]">
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
