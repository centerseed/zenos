"use client";

import Link from "next/link";
import type { Entity } from "@/types";
import { useInk } from "@/lib/zen-ink/tokens";
import { Panel } from "@/components/zen/Panel";
import { Chip } from "@/components/zen/Chip";

interface ProjectCardProps {
  entity: Entity;
  moduleCount: number;
}

const statusColors: Record<string, string> = {
  active: "bg-green-900/50 text-green-400",
  paused: "bg-yellow-900/50 text-yellow-400",
  planned: "bg-blue-900/50 text-blue-400",
  completed: "bg-secondary text-muted-foreground",
};

export function ProjectCard({ entity, moduleCount }: ProjectCardProps) {
  const t = useInk("light");
  return (
    <Link href={`/projects?id=${entity.id}`}>
      <Panel t={t} className="cursor-pointer transition-all hover:shadow-sm" style={{ boxShadow: "0 6px 18px rgba(58,52,44,0.06)" }}>
        <div className="px-4 pt-4">
          <div className="flex items-start justify-between mb-1">
            <h3 className="text-lg font-semibold text-foreground">{entity.name}</h3>
            <span className={statusColors[entity.status] ?? "text-muted-foreground"}>
              <Chip t={t} tone="muted">
              {entity.status}
              </Chip>
            </span>
          </div>
        </div>
        <div className="px-4">
          <p className="text-muted-foreground text-sm mb-4 line-clamp-2">
            {entity.summary}
          </p>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>{moduleCount} modules</span>
          <span>
            Updated{" "}
            {entity.updatedAt.toLocaleDateString("zh-TW")}
          </span>
          </div>
        </div>
      </Panel>
    </Link>
  );
}
