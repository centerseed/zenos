"use client";

import { useMemo } from "react";
import type { Entity, Relationship, Blindspot, Task } from "@/types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import {
  NODE_TYPE_COLORS,
  NODE_TYPE_LABELS,
} from "@/lib/constants";

interface NodeDetailSheetProps {
  entity: Entity | null;
  relationships: Relationship[];
  blindspots: Blindspot[];
  entities: Entity[];
  tasks: Task[];
  onClose: () => void;
  onHoverNode?: (nodeId: string | null) => void;
  onFocusNode?: (nodeId: string) => void;
}

const STATUS_BADGE_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  planned: "bg-cyan-500/20 text-cyan-400",
};

const TASK_STATUS_LABELS: Record<string, string> = {
  in_progress: "In Progress",
  review: "Review",
  todo: "Todo",
};

export default function NodeDetailSheet({
  entity,
  relationships,
  blindspots,
  entities,
  tasks,
  onClose,
  onHoverNode,
  onFocusNode,
}: NodeDetailSheetProps) {
  const entityMap = useMemo(() => new Map(entities.map((e) => [e.id, e])), [entities]);

  // Filter relationships relevant to this entity
  const relevantRels = useMemo(() => {
    if (!entity) return [];
    return relationships.filter(
      (r) => r.sourceEntityId === entity.id || r.targetId === entity.id
    );
  }, [entity, relationships]);

  // Action Layer: Tasks
  const categorizedTasks = useMemo(() => {
    if (!entity) return { inProgress: [], review: [], backlog: [] };
    const related = tasks.filter((t) => t.linkedEntities.includes(entity.id));
    return {
      inProgress: related.filter((t) => t.status === "in_progress"),
      review: related.filter((t) => t.status === "review"),
      backlog: related.filter((t) => t.status === "todo"),
    };
  }, [entity, tasks]);

  // Reference Layer: Documents
  const categorizedDocs = useMemo(() => {
    if (!entity) return { specs: [], adrs: [], sources: [] };
    const childDocs = entities.filter((e) => e.parentId === entity.id && e.type === "document");
    const specs = childDocs.filter((d) => d.name.startsWith("SPEC-"));
    const adrs = childDocs.filter((d) => d.name.startsWith("ADR-"));
    const otherDocs = childDocs.filter((d) => !d.name.startsWith("SPEC-") && !d.name.startsWith("ADR-"));
    
    return {
      specs,
      adrs,
      sources: [...(entity.sources || []), ...otherDocs.flatMap(d => d.sources || [])],
    };
  }, [entity, entities]);

  const hasTasks = categorizedTasks.inProgress.length > 0 || categorizedTasks.review.length > 0 || categorizedTasks.backlog.length > 0;
  const hasDocs = categorizedDocs.specs.length > 0 || categorizedDocs.adrs.length > 0 || categorizedDocs.sources.length > 0;

  return (
    <Sheet open={!!entity} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="bg-card border-border text-foreground overflow-y-auto sm:max-w-md p-0"
      >
        {entity && (
          <div className="flex flex-col h-full">
            <div className="p-6 border-b border-border bg-card sticky top-0 z-10">
              <SheetHeader className="space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge
                      className="text-foreground/80 font-medium"
                      style={{ backgroundColor: `${NODE_TYPE_COLORS[entity.type] ?? "#6366F1"}33` }}
                    >
                      {NODE_TYPE_LABELS[entity.type] ?? entity.type}
                    </Badge>
                    {entity.level != null && (
                      <Badge variant="outline" className="border-foreground/20 text-foreground/50 font-mono text-xs">
                        L{entity.level}
                      </Badge>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {!entity.confirmedByUser && (
                      <Badge variant="outline" className="border-orange-500/50 text-orange-400 bg-orange-500/5">draft</Badge>
                    )}
                    <Badge
                      className={STATUS_BADGE_COLORS[entity.status] ?? "bg-gray-500/20 text-gray-400"}
                    >
                      {entity.status}
                    </Badge>
                  </div>
                </div>
                <SheetTitle className="text-2xl font-bold text-foreground pt-2">
                  {entity.name}
                </SheetTitle>
              </SheetHeader>
              <p className="text-sm text-foreground/70 leading-relaxed mt-3">
                {entity.summary}
              </p>
            </div>

            <div className="flex flex-col gap-8 p-6">
              {/* Action Layer (Tasks) */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                  Action Layer (Tasks)
                </h3>
                {!hasTasks ? (
                  <p className="text-xs text-foreground/30 italic">No active tasks</p>
                ) : (
                  <div className="space-y-4">
                    {[
                      { label: "Review", items: categorizedTasks.review, color: "text-amber-400" },
                      { label: "In Progress", items: categorizedTasks.inProgress, color: "text-blue-400" },
                      { label: "Todo", items: categorizedTasks.backlog, color: "text-foreground/40" },
                    ].map((group) => group.items.length > 0 && (
                      <div key={group.label}>
                        <div className={`text-[10px] font-semibold uppercase mb-2 ${group.color}`}>
                          {group.label}
                        </div>
                        <div className="space-y-1.5">
                          {group.items.map((task) => (
                            <div
                              key={task.id}
                              onMouseEnter={() => onHoverNode?.(entity.id)}
                              onMouseLeave={() => onHoverNode?.(null)}
                              className="group flex items-start gap-2 p-2 rounded-md bg-foreground/5 hover:bg-foreground/10 transition-colors border border-transparent hover:border-border/50"
                            >
                              <div className="w-1 h-4 rounded-full mt-0.5 shrink-0 bg-orange-500/40" />
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground/80 truncate group-hover:text-foreground transition-colors">
                                  {task.title}
                                </div>
                                {task.assignee && (
                                  <div className="text-[10px] text-foreground/40 mt-0.5">
                                    @{task.assignee}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Reference Layer (Docs) */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
                  Reference Layer (Docs)
                </h3>
                {!hasDocs ? (
                  <p className="text-xs text-foreground/30 italic">No reference documents</p>
                ) : (
                  <div className="space-y-4">
                    {[
                      { label: "Core Specs", items: categorizedDocs.specs, type: 'entity' },
                      { label: "Decisions", items: categorizedDocs.adrs, type: 'entity' },
                      { label: "External Sources", items: categorizedDocs.sources, type: 'source' },
                    ].map((group) => group.items.length > 0 && (
                      <div key={group.label}>
                        <div className="text-[10px] font-semibold uppercase mb-2 text-cyan-400/70">
                          {group.label}
                        </div>
                        <div className="space-y-1">
                          {group.items.map((item, idx) => (
                            <div
                              key={group.type === 'entity' ? (item as Entity).id : `src-${idx}`}
                              className="flex items-center gap-2 py-1.5 group cursor-pointer"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-foreground/30 group-hover:text-cyan-400 transition-colors">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
                              </svg>
                              <span className="text-xs text-foreground/70 group-hover:text-foreground truncate transition-colors">
                                {group.type === 'entity' ? (item as Entity).name : (item as any).label}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Dependency Layer */}
              <section>
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground/40 mb-3">
                  Dependency Layer
                </h3>
                <div className="space-y-3">
                  {[
                    { label: "Depends on", direction: "out", color: "text-blue-400/60" },
                    { label: "Serves", direction: "in", color: "text-emerald-400/60" },
                  ].map((dir) => {
                    const filtered = relevantRels.filter(r => 
                      dir.direction === "out" ? r.sourceEntityId === entity.id : r.targetId === entity.id
                    );
                    if (filtered.length === 0) return null;
                    return (
                      <div key={dir.label}>
                        <div className={`text-[10px] font-medium mb-1.5 ${dir.color}`}>{dir.label}</div>
                        <div className="flex flex-wrap gap-1.5">
                          {filtered.map(rel => {
                            const targetId = dir.direction === "out" ? rel.targetId : rel.sourceEntityId;
                            const target = entityMap.get(targetId);
                            if (!target) return null;
                            return (
                              <button
                                key={rel.id}
                                onClick={() => onFocusNode?.(target.id)}
                                onMouseEnter={() => onHoverNode?.(target.id)}
                                onMouseLeave={() => onHoverNode?.(null)}
                                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-foreground/5 border border-border/40 hover:border-foreground/20 hover:bg-foreground/10 transition-all text-xs text-foreground/70"
                              >
                                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_TYPE_COLORS[target.type] }} />
                                {target.name}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Blindspots */}
              {blindspots.length > 0 && (
                <section>
                  <h3 className="text-xs font-bold uppercase tracking-widest text-red-400/60 mb-3">
                    Active Blindspots
                  </h3>
                  <div className="space-y-2">
                    {blindspots.map((bs) => (
                      <div
                        key={bs.id}
                        className={`rounded-lg p-3 text-xs ${
                          bs.severity === "red"
                            ? "bg-red-500/10 border border-red-500/20 text-red-300/80"
                            : "bg-yellow-500/10 border border-yellow-500/20 text-yellow-300/80"
                        }`}
                      >
                        <p className="font-semibold mb-1">{bs.description}</p>
                        {bs.suggestedAction && (
                          <p className="opacity-60 text-[10px] leading-tight">
                            Suggest: {bs.suggestedAction}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
