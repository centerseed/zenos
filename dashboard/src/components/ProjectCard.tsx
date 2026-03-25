"use client";

import Link from "next/link";
import type { Entity } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
  return (
    <Link href={`/projects?id=${entity.id}`}>
      <Card className="ring-1 ring-border/80 hover:ring-blue-700/40 hover:shadow-sm transition-all cursor-pointer">
        <CardHeader>
          <div className="flex items-start justify-between mb-1">
            <CardTitle className="text-lg font-semibold text-foreground">{entity.name}</CardTitle>
            <span
              className={`text-xs px-2 py-1 rounded-full ${statusColors[entity.status] ?? "bg-secondary text-muted-foreground"}`}
            >
              {entity.status}
            </span>
          </div>
        </CardHeader>
        <CardContent>
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
        </CardContent>
      </Card>
    </Link>
  );
}
